"""收集 .NET API 與 Angular 專案的第三方套件直接參考、授權中繼資料與原始碼使用證據，輸出 JSON。

用法：
  python -I collect_packages.py <入口> [<入口> ...] [--include-first-party] [--no-usage]

入口：
  .NET     .csproj／.fsproj／.vbproj（沿 ProjectReference 遞迴展開）或 .sln
  Angular  package.json（同目錄有 angular.json 時一併解析 styles／scripts／assets／builder）
  目錄     只看最上層的上述檔案，不遞迴掃整個 repo

只收直接參考，不展開遞移相依。授權讀自本機套件快取（~/.nuget/packages、node_modules），
讀不到時欄位留空，由呼叫端另行查證，不要猜。
usage.status 只有 found／not-found 兩種；not-found 是「自動偵測沒命中」，不等於可移除。
"""
import json
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# .NET 平台／Microsoft 自家套件的前綴，預設排除
FIRST_PARTY_PREFIXES = ("microsoft.", "system.", "runtime.", "netstandard.", "azure.")
DOTNET_PROJECT_EXT = (".csproj", ".fsproj", ".vbproj")
DOTNET_SOURCE_EXT = (".cs", ".cshtml", ".razor", ".vb", ".fs")
# 與框架共用、搜尋會誤判的命名空間根（套件常在此放擴充方法）
SHARED_NAMESPACE_ROOTS = ("System", "Microsoft.Extensions", "Microsoft.AspNetCore", "Microsoft.EntityFrameworkCore")
# Angular 框架核心：列為 framework 類別，報告可合併成一列
ANGULAR_FRAMEWORK = ("@angular/", "@angular-devkit/", "rxjs", "zone.js", "tslib")
# angular.json 存在時視為一定會用到的建置／測試工具鏈
ANGULAR_IMPLICIT = ("typescript", "tslib", "@angular/compiler", "@angular/compiler-cli",
                    "@angular/language-service", "@schematics/angular", "sass")
NPM_SOURCE_EXT =(".ts", ".js", ".mjs", ".cjs", ".scss", ".sass", ".less", ".css")
SKIP_DIRS = {"node_modules", "bin", "obj", "dist", ".angular", ".git", "coverage", "packages", ".vs"}
SAMPLE_LIMIT = 5


def strip_ns(tag):
    """去掉 XML 命名空間，回傳純標籤名。"""
    return tag.rsplit("}", 1)[-1]


def iter_files(root, exts):
    """遞迴列出 root 底下指定副檔名的檔案，略過建置輸出與相依目錄。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f.endswith(exts):
                yield Path(dirpath) / f


def read_text(path):
    """以 UTF-8 讀檔，失敗時回空字串。"""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def new_usage():
    """建立空的使用證據結構。"""
    return {"status": "not-found", "files": 0, "byProject": {}, "samples": [], "via": []}


def add_hit(usage, project, rel_path, via):
    """記錄一筆使用證據。"""
    usage["status"] = "found"
    usage["files"] += 1
    usage["byProject"][project] = usage["byProject"].get(project, 0) + 1
    if len(usage["samples"]) < SAMPLE_LIMIT:
        usage["samples"].append(rel_path)
    if via not in usage["via"]:
        usage["via"].append(via)


# ---------------------------------------------------------------- .NET

def assembly_namespaces(dll_path):
    """解析 .NET 組件的 ECMA-335 中繼資料，回傳公開型別的命名空間集合；非受控 DLL 回空集合。"""
    try:
        data = dll_path.read_bytes()
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        if data[pe:pe + 4] != b"PE\0\0":
            return set()
        sections = struct.unpack_from("<H", data, pe + 6)[0]
        opt_size = struct.unpack_from("<H", data, pe + 20)[0]
        opt = pe + 24
        magic = struct.unpack_from("<H", data, opt)[0]
        cli_rva = struct.unpack_from("<I", data, opt + (96 if magic == 0x10B else 112) + 14 * 8)[0]
        if not cli_rva:
            return set()
        sec_table = [struct.unpack_from("<IIII", data, opt + opt_size + i * 40 + 8) for i in range(sections)]

        def offset(rva):
            for vsize, vaddr, rawsize, rawptr in sec_table:
                if vaddr <= rva < vaddr + max(vsize, rawsize):
                    return rva - vaddr + rawptr
            raise ValueError("RVA 不在任何 section")

        md = offset(struct.unpack_from("<I", data, offset(cli_rva) + 8)[0])
        ver_len = struct.unpack_from("<I", data, md + 12)[0]
        pos = md + 16 + ver_len
        stream_count = struct.unpack_from("<H", data, pos + 2)[0]
        pos += 4
        streams = {}
        for _ in range(stream_count):
            s_off = struct.unpack_from("<I", data, pos)[0]
            end = data.index(b"\0", pos + 8)
            streams[data[pos + 8:end].decode()] = md + s_off
            pos = (end + 4) & ~3
        tables = streams.get("#~") or streams.get("#-")
        strings = streams["#Strings"]
        heap_sizes = data[tables + 6]
        valid = struct.unpack_from("<Q", data, tables + 8)[0]
        rows, pos = {}, tables + 24
        for i in range(64):
            if valid >> i & 1:
                rows[i] = struct.unpack_from("<I", data, pos)[0]
                pos += 4
        str_size = 4 if heap_sizes & 1 else 2
        guid_size = 4 if heap_sizes & 2 else 2

        def idx_size(*tbls, bits=0):
            return 2 if max(rows.get(t, 0) for t in tbls) < (1 << (16 - bits)) else 4

        module_row = 2 + str_size + guid_size * 3
        typeref_row = idx_size(0, 26, 35, 1, bits=2) + str_size * 2
        typedef_row = 4 + str_size * 2 + idx_size(2, 1, 27, bits=2) + idx_size(4) + idx_size(6)
        pos += rows.get(0, 0) * module_row + rows.get(1, 0) * typeref_row
        fmt = "<I" if str_size == 4 else "<H"

        namespaces = set()
        for r in range(rows.get(2, 0)):
            row = pos + r * typedef_row
            flags = struct.unpack_from("<I", data, row)[0]
            ns_index = struct.unpack_from(fmt, data, row + 4 + str_size)[0]
            if flags & 0x7 == 1 and ns_index:  # Public、非巢狀
                start = strings + ns_index
                namespaces.add(data[start:data.index(b"\0", start)].decode("utf-8", "ignore"))
        return namespaces
    except (ValueError, struct.error, IndexError, KeyError, OSError, TypeError):
        return set()


def is_shared_namespace(namespace):
    """判斷命名空間是否落在與框架共用的根（套件在此通常只放 DI 擴充方法）。"""
    return any(namespace == root or namespace.startswith(root + ".") for root in SHARED_NAMESPACE_ROOTS)


def minimal_prefixes(namespaces):
    """把命名空間集合壓成最短前綴集合（NPOI.SS、NPOI.XSSF → NPOI），並排除與框架共用的根。"""
    result = []
    for n in sorted(n for n in namespaces if not is_shared_namespace(n)):
        if not any(n == p or n.startswith(p + ".") for p in result):
            result.append(n)
    return result


def find_central_versions(project_path):
    """往上層找 Directory.Packages.props，回傳中央版本管理的 {套件小寫名: 版本}。"""
    versions = {}
    for parent in [project_path.parent, *project_path.parents]:
        props = parent / "Directory.Packages.props"
        if props.exists():
            for el in ET.parse(props).getroot().iter():
                if strip_ns(el.tag) == "PackageVersion":
                    name = el.get("Include") or el.get("Update")
                    if name:
                        versions[name.lower()] = el.get("Version") or ""
            break
    return versions


def read_nuget_package(name, version):
    """從 NuGet 全域快取讀 nuspec 與 lib 組件，回傳 (授權中繼資料, 命名空間清單, 是否只有原生庫, 是否有框架共用命名空間)。"""
    root = Path(os.environ.get("NUGET_PACKAGES", Path.home() / ".nuget" / "packages"))
    pkg_dir = root / name.lower() / version.lower()
    if not pkg_dir.exists():
        return {}, [], False, False
    meta = {}
    nuspecs = list(pkg_dir.glob("*.nuspec"))
    if nuspecs:
        for el in ET.parse(nuspecs[0]).getroot().iter():
            tag = strip_ns(el.tag)
            text = (el.text or "").strip()
            if tag == "license":
                # type="file" 時內容是套件內的檔名，需另讀檔判斷授權
                meta["license"] = text if el.get("type") == "expression" else f"file:{pkg_dir / text}"
            elif tag == "licenseUrl" and "deprecateLicenseUrl" not in text:
                meta.setdefault("licenseUrl", text)
            elif tag in ("description", "projectUrl", "authors") and text:
                meta.setdefault(tag, text)
    namespaces = set()
    dlls = list((pkg_dir / "lib").rglob("*.dll")) or list((pkg_dir / "ref").rglob("*.dll"))
    for dll in dlls:
        namespaces |= assembly_namespaces(dll)
    native_only = not dlls and (pkg_dir / "runtimes").exists()
    has_extensions = any(is_shared_namespace(n) for n in namespaces)
    return meta, minimal_prefixes(namespaces), native_only, has_extensions


def projects_from_sln(sln):
    """從 .sln 取出所有 .NET 專案路徑。"""
    found = re.findall(r'Project\("[^"]+"\)\s*=\s*"[^"]*",\s*"([^"]+\.(?:cs|fs|vb)proj)"', read_text(sln))
    return [(sln.parent / p.replace("\\", os.sep)).resolve() for p in found]


def collect_dotnet(entry, include_first_party, seen, out):
    """解析一個 .NET 專案的 PackageReference，並沿 ProjectReference 遞迴。"""
    entry = entry.resolve()
    if entry in seen or not entry.exists():
        return
    seen[entry] = entry.stem
    central = find_central_versions(entry)
    for el in ET.parse(entry).getroot().iter():
        tag = strip_ns(el.tag)
        if tag == "ProjectReference":
            ref = el.get("Include", "").replace("\\", os.sep)
            collect_dotnet((entry.parent / ref).resolve(), include_first_party, seen, out)
        elif tag == "PackageReference":
            name = el.get("Include") or el.get("Update")
            if not name or (not include_first_party and name.lower().startswith(FIRST_PARTY_PREFIXES)):
                continue
            version = el.get("Version") or el.get("VersionOverride") or ""
            if not version:
                child_ver = next((c for c in el if strip_ns(c.tag) == "Version"), None)
                version = (child_ver.text or "").strip() if child_ver is not None else central.get(name.lower(), "")
            item = out.setdefault(("nuget", name.lower()), {
                "ecosystem": "nuget", "name": name, "category": "runtime", "versions": {}, "projects": []})
            item["versions"].setdefault(version, []).append(entry.stem)
            item["projects"].append(entry.stem)
            if "meta" not in item:
                item["meta"], item["namespaces"], item["nativeOnly"], item["diExtensions"] = read_nuget_package(name, version)
            if el.get("PrivateAssets") or any(strip_ns(c.tag) == "PrivateAssets" for c in el):
                item["category"] = "build"


def scan_dotnet_usage(seen, packages):
    """搜尋所有已掃描 .NET 專案的原始碼與設定檔，以套件命名空間判斷使用情形。"""
    dir_to_project = {p.parent: name for p, name in seen.items()}

    def owner(path):
        # 取最深層（最接近檔案）的專案目錄
        for parent in path.parents:
            if parent in dir_to_project:
                return dir_to_project[parent]
        return "?"

    patterns = {}
    for item in packages:
        item["usage"] = new_usage()
        if item.get("namespaces"):
            alt = "|".join(re.escape(n) for n in item["namespaces"])
            # using 宣告、global using、別名 using，或完整限定名稱
            patterns[item["name"]] = re.compile(rf"(?<![\w.])(?:{alt})\b(?=\s*[.;])")
        if item.get("nativeOnly"):
            item["usage"]["hint"] = "原生庫，由包裝套件載入；包裝套件使用中即視為使用中"
        elif item.get("diExtensions"):
            item["usage"]["hint"] = "套件在 Microsoft.Extensions／AspNetCore 命名空間放了擴充方法，未命中時查 Startup／Program 的 AddXxx／UseXxx 呼叫"
    dirs = list(dir_to_project)
    roots = sorted({d for d in dirs if not any(o in d.parents for o in dirs)})
    for root in roots:
        for path in iter_files(root, DOTNET_SOURCE_EXT + (".config", ".json")):
            text = read_text(path)
            rel = str(path.relative_to(root.parent))
            proj = owner(path)
            for item in packages:
                if path.suffix in DOTNET_SOURCE_EXT:
                    pat = patterns.get(item["name"])
                    if pat and pat.search(text):
                        add_hit(item["usage"], proj, rel, "source")
                elif path.name != "packages.lock.json" and re.search(rf"\b{re.escape(item['name'])}\b", text):
                    # NLog.config、appsettings 的套件設定區段
                    add_hit(item["usage"], proj, rel, "config")


# ---------------------------------------------------------------- Angular／npm

SPECIFIER_RE = re.compile(
    r"""(?:\bfrom\s+|\bimport\s*\(\s*|\brequire\s*\(\s*|\bimport\s+)['"]([^'".][^'"]*)['"]"""
    r"""|@(?:import|use|forward)\s+['"]~?([^'".][^'"]*)['"]""")


def package_of(specifier):
    """把 import 路徑轉成套件名（@scope/name/sub → @scope/name，name/sub → name）。"""
    parts = specifier.lstrip("~").split("/")
    return "/".join(parts[:2]) if parts[0].startswith("@") else parts[0]


def json_strings(node):
    """遞迴取出 JSON 內所有字串值。"""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from json_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from json_strings(v)


def tsconfig_types(base):
    """收集 tsconfig*.json 的 compilerOptions.types 名單（tsconfig 可能有註解，用正規式取）。"""
    types = set()
    for ts in list(base.glob("tsconfig*.json")) + list((base / "src").glob("tsconfig*.json")):
        for block in re.findall(r'"types"\s*:\s*\[([^\]]*)\]', read_text(ts)):
            types |= set(re.findall(r'"([^"]+)"', block))
    return types


def collect_npm(entry, out, scan_usage):
    """解析 package.json 的 dependencies／devDependencies，授權讀 node_modules，並偵測 Angular 專案的使用情形。"""
    entry = entry.resolve()
    base = entry.parent
    data = json.loads(entry.read_text(encoding="utf-8"))
    project = data.get("name") or base.name
    items = []
    for section in ("dependencies", "devDependencies"):
        for name, spec in (data.get(section) or {}).items():
            installed = base / "node_modules" / name / "package.json"
            meta, version, bins, peers = {}, "", [], []
            if installed.exists():
                pkg = json.loads(installed.read_text(encoding="utf-8"))
                version = pkg.get("version", "")
                lic = pkg.get("license") or pkg.get("licenses")
                if isinstance(lic, list):
                    lic = " OR ".join(x.get("type", "") if isinstance(x, dict) else str(x) for x in lic)
                meta = {
                    "license": lic.get("type") if isinstance(lic, dict) else lic,
                    "description": pkg.get("description"),
                    "projectUrl": pkg.get("homepage"),
                    "deprecated": pkg.get("deprecated"),
                }
                b = pkg.get("bin")
                bins = list(b) if isinstance(b, dict) else ([name.split("/")[-1]] if b else [])
                peers = list(pkg.get("peerDependencies") or {})
            if name.startswith(ANGULAR_FRAMEWORK):
                category = "framework"
            elif name.startswith("@types/"):
                category = "types"
            else:
                category = "dev" if section == "devDependencies" else "runtime"
            item = out.setdefault(("npm", f"{base}:{name}"), {
                "ecosystem": "npm", "name": name, "versions": {}, "projects": []})
            item.update({"spec": spec, "category": category, "meta": meta, "bins": bins, "peers": peers,
                         "installed": installed.exists()})
            item["versions"].setdefault(version or spec, []).append(project)
            item["projects"].append(project)
            items.append(item)
    if scan_usage:
        scan_npm_usage(base, project, data, items)


def scan_npm_usage(base, project, data, items):
    """以 import／SCSS／angular.json／npm scripts／tsconfig types／karma 設定判斷 npm 套件是否被使用。"""
    by_name = {i["name"]: i for i in items}
    for i in items:
        i["usage"] = new_usage()

    def hit(name, rel, via):
        if name in by_name:
            add_hit(by_name[name]["usage"], project, rel, via)

    # 原始碼與根目錄設定檔（karma.conf.js、protractor.conf.js 等）
    files = list(iter_files(base / "src", NPM_SOURCE_EXT)) if (base / "src").exists() else []
    files += [p for p in base.iterdir() if p.is_file() and p.suffix in (".js", ".ts", ".mjs", ".cjs")]
    for path in files:
        found = {package_of(a or b) for a, b in SPECIFIER_RE.findall(read_text(path))}
        for name in found:
            hit(name, str(path.relative_to(base)), "source")
    # angular.json：builder、styles、scripts、assets 引用 node_modules
    ng = base / "angular.json"
    if ng.exists():
        for s in set(json_strings(json.loads(read_text(ng)))):
            m = re.match(r"(?:\./)?node_modules/((?:@[^/]+/)?[^/]+)", s)
            if m:
                hit(m.group(1), "angular.json", "angular.json styles/scripts/assets")
            elif re.match(r"^(?:@[\w.-]+/)?[\w.-]+:[\w-]+$", s):
                hit(s.split(":")[0], "angular.json", "angular.json builder")
    # npm scripts 呼叫的 CLI
    tokens = set(re.findall(r"[@\w./-]+", " ".join((data.get("scripts") or {}).values())))
    for i in items:
        if tokens & (set(i.get("bins", [])) | {i["name"]}):
            hit(i["name"], "package.json scripts", "npm scripts")
    # tsconfig types 與 @types 對應的本體套件
    types = tsconfig_types(base)
    for i in items:
        if i["name"].startswith("@types/"):
            short = i["name"][7:]
            target = "@" + short.replace("__", "/") if "__" in short else short
            if short in types:
                hit(i["name"], "tsconfig types", "tsconfig types")
            elif target in by_name and by_name[target]["usage"]["status"] == "found":
                hit(i["name"], f"（{target} 的型別定義）", "types-of-used-package")
    # Angular 工具鏈隱含使用：不會出現在 import，但 ng build／ng test 需要
    if ng.exists():
        for name in ANGULAR_IMPLICIT:
            if name in by_name and by_name[name]["usage"]["status"] != "found":
                hit(name, "angular.json", "implicit（Angular 工具鏈）")
    if any(base.glob("karma.conf.*")):
        hit("karma", "karma.conf", "karma 設定檔")
    # 已使用套件的 peerDependencies：反覆傳遞直到沒有新增
    changed = True
    while changed:
        changed = False
        for user in items:
            if user["usage"]["status"] != "found":
                continue
            for peer in user.get("peers", []):
                if peer in by_name and by_name[peer]["usage"]["status"] != "found":
                    hit(peer, f"（{user['name']} 的 peerDependency）", f"peer of {user['name']}")
                    changed = True


# ---------------------------------------------------------------- main

def main(argv):
    include_first_party = "--include-first-party" in argv
    scan_usage = "--no-usage" not in argv
    entries = [Path(a) for a in argv if not a.startswith("--")]
    if not entries:
        print(__doc__, file=sys.stderr)
        return 2
    out, seen, roots = {}, {}, []
    for entry in entries:
        files = [entry] if entry.is_file() else sorted(
            p for p in entry.iterdir()
            if p.suffix in DOTNET_PROJECT_EXT + (".sln",) or p.name == "package.json")
        for f in files:
            roots.append(str(f))
            if f.suffix == ".sln":
                for proj in projects_from_sln(f):
                    collect_dotnet(proj, include_first_party, seen, out)
            elif f.suffix in DOTNET_PROJECT_EXT:
                collect_dotnet(f, include_first_party, seen, out)
            elif f.name == "package.json":
                collect_npm(f, out, scan_usage)
    nuget = [i for k, i in out.items() if k[0] == "nuget"]
    if scan_usage and nuget:
        scan_dotnet_usage(seen, nuget)
    packages = []
    for item in out.values():
        item["projects"] = sorted(set(item["projects"]))
        item["versionConflict"] = len(item["versions"]) > 1
        item.pop("bins", None)
        item.pop("peers", None)
        packages.append(item)
    result = {
        "entries": roots,
        "projectsScanned": sorted(set(seen.values())),
        "packages": sorted(packages, key=lambda p: (p["ecosystem"], p.get("category", ""), p["name"].lower())),
    }
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
