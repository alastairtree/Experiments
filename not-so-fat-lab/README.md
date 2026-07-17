# not-so-fat-lab

A deliberately **slim, batch-only** MATLAB base image.

It exists to be a small, fast-to-pull foundation for containers that run
`matlab -batch` jobs — data pipelines, scheduled processing, CI — and never a
UI. The stock `mathworks/matlab` images are built for the interactive
browser/desktop experience and carry the whole VNC / `matlab-proxy` / desktop
stack with them; none of that is needed for batch, so this image throws it away
and starts from the smallest base MATLAB officially supports.

On top of MATLAB it bakes in the things our jobs actually need and nothing else:

* the requested MATLAB toolboxes (configurable — see [`ADDITIONAL_PRODUCTS`](#build-arguments)),
* NASA's **SPICE toolkit for MATLAB (MICE)** and the **NASA CDF** MATLAB patch,
  both already on the MATLAB search path,
* the **[`uv`](https://docs.astral.sh/uv/)** Python package/version manager on
  `PATH`, so downstream images can add Python and packages later.

It is intended as a **base image**: build `FROM` it, add your code, set your
entrypoint.

---

## Why it is smaller

| Technique | Effect |
|---|---|
| **UBI8-minimal** base (`microdnf`) instead of full UBI8 / Ubuntu | smallest MathWorks-supported base; ~140 MB vs ~300 MB (UBI8) / ~1.35 GB (`matlab-deps`) |
| **Pruned, batch-only dependency set** (see `base-dependencies.txt`) | drops the desktop stack — `gtk3`, `pango`, `cairo`, `glibc-locale-source`, etc. — that batch never loads |
| **Post-install pruning of MATLAB itself** (see [What's stripped out](#whats-stripped-out-and-why)) | deletes ~730 MB of UI, docs, online-service and non-English payloads the MATLAB install ships but batch never touches |
| **Multi-stage build** | `mpm`, `curl`, `tar`/`unzip`, package-manager caches and install logs stay in the throwaway *installer* stage and never reach the shipped image |
| **No desktop / proxy stack** | unlike `mathworks/matlab`, there is no VNC, no `matlab-proxy`, no supervisor |

Savings come from the base OS, the dependency diet, leaving all build tooling
behind, **and** carving the batch-irrelevant payloads out of the MATLAB install.

See [Image sizes](#image-sizes) for measured numbers.

---

## How the image is built

A three-stage build (see [`Dockerfile`](Dockerfile)); no MATLAB licence is
needed to build — `mpm` only downloads and installs.

1. **`uv` stage** — the official `ghcr.io/astral-sh/uv` image, used purely as a
   source to `COPY` the static `uv` / `uvx` binaries from. No installer script,
   nothing to clean up.

2. **`installer` stage** — full UBI8, entirely throwaway. It does all the heavy,
   single-use work:
   * installs MATLAB + the requested toolboxes with **`mpm`** (MATLAB Package
     Manager) into `/opt/matlab/<release>`;
   * downloads and unpacks **NASA MICE** and the **NASA CDF** patch, keeping only
     the bits MATLAB loads at runtime;
   * **prunes** every batch-irrelevant tree from the MATLAB install
     ([details below](#whats-stripped-out-and-why)).
   All the fetch/unpack tooling (`mpm`, `curl`, `tar`, caches, logs) lives and
   dies here.

3. **`runtime` stage** — UBI8-minimal, the shipped image. It:
   * installs only the pruned, batch-only shared-library set from
     `base-dependencies.txt` (via `microdnf`);
   * copies `uv` from stage 1 and the finished `/opt/matlab`, `/opt/naif`,
     `/opt/cdf` trees from the installer stage;
   * sets `PATH` and `MATLABPATH` (so MICE + CDF auto-resolve), creates the
     non-root `matlab` user, and defaults `ENTRYPOINT ["matlab"]`.

Because only the finished trees are copied forward, none of the build tooling or
caches reach the final image.

---

## What's stripped out (and why)

Two categories: OS packages that are never installed, and MATLAB payloads
deleted right after install. **Everything below was verified against a real
network licence server** to leave `matlab -batch` — plus MICE, the NASA CDF
patch, and an FFT / stats / matrix / Signal-Toolbox compute check — fully
working.

### Batch-only OS dependency set

`base-dependencies.txt` installs only the shared libraries MATLAB `dlopen`s to
start headless — not the full [`matlab-deps`](https://github.com/mathworks-ref-arch/container-images)
desktop set (`gtk3`, `pango`, `cairo`, `glibc-locale-source`, …).

> One entry is easy to miss: **`mesa-libgbm`**. The R2026a engine `dlopen`s
> `libgbm.so.1` at start-up. It is *not* a linked dependency, so `ldd` never
> reveals it — and without it `matlab -batch` dies **silently with exit 127
> before printing anything**. Do not drop it when pruning further.

### MATLAB payloads removed after install (~730 MB)

| Removed | ~Size | Why it's safe for batch |
|---|--:|---|
| `sys/mwds` — MathWorks Service Host | 395 MB | online-account / add-on-explorer / cloud-connector daemon; unused under network (`MLM_LICENSE_FILE`) licensing |
| non-English localisation (`ja`, `ko`, `zh_CN`, `zh_TW`, `de_DE`, `fr_FR`, `es_ES`, `it_IT`, `pt_BR`, `ru_RU`) | 176 MB | English is kept |
| MICE extras (`doc`, `exe`, C sources, headers, `.a` archives) | 115 MB | only `mice/lib/mice.mexa64` + `mice/src/mice` are on `MATLABPATH` |
| in-product HTML `help/` | 60 MB | command-line `help <fn>` still works (it reads each function's `.m` header, not this tree) |
| `cef_locales` + `cef_rcf` | 47 MB | Chromium UI resource payload — batch renders no UI |
| `mwdocsearch` + `docsearch_server` | 26 MB | in-product documentation search |
| `ARIALUNI.TTF` | 22 MB | Live Editor font |
| `sys/fluxbox` | 2 MB | desktop window manager |

### Deliberately kept

* **`libcef.so` (227 MB)** — the engine hard-loads it at start-up; removing it
  reproduces the silent exit-127 death, so only its resource payload (above)
  goes.
* **The JRE (`sys/java`, 134 MB)** — many functions, and the MATLAB Report
  Generator, need the JVM.
* **Data-I/O libraries** — `libxl` (Excel, 36 MB), `libmwarrow` (Parquet/Arrow,
  33 MB), `libduckdb` (46 MB). Common in real batch data pipelines.
* **GPU/CUDA + software-render libs (~148 MB)** — removable if your jobs are
  strictly CPU-only and never render figures; kept in for generality. See the
  optional trims discussed in the commit history if you want them out.
* **Per-toolbox doc trees** (`demos` / `html` / `help`, ~30 MB) — these are
  registered in MATLAB's search path (`pathdef.m`), so deleting them makes
  MATLAB print "nonexistent directory" warnings on *every* start-up. Not worth
  polluting every job's log for 30 MB.

---

## Usage

### Run a batch job

MATLAB needs a licence at **run** time (none is needed to build the image).
Point it at a network licence manager (or mount a licence file):

```bash
docker run --rm \
  -e MLM_LICENSE_FILE=27000@license.example.com \
  ghcr.io/alastairtree/not-so-fat-lab:latest \
  -batch "ver; disp(pi)"
```

The default `ENTRYPOINT` is `matlab`, so everything after the image name is
passed straight to MATLAB. Running with no arguments prints MATLAB's usage
(`-help`), which needs neither a licence nor a display.

### Use it as a base image

```dockerfile
FROM ghcr.io/alastairtree/not-so-fat-lab:latest

USER root
# add Python + packages with the bundled uv, or install more OS packages
RUN uv venv /opt/venv && /opt/venv/bin/uv pip install numpy spiceypy
COPY my_pipeline/ /app/
USER matlab

ENTRYPOINT ["matlab"]
CMD ["-batch", "run('/app/main.m')"]
```

### NASA MICE and CDF

Both toolkits are on `MATLABPATH`, so their functions resolve automatically in
any MATLAB session — no `addpath` required:

```matlab
cspice_furnsh('/data/kernels/naif0012.tls');   % MICE (SPICE)
info = spdfcdfinfo('/data/example.cdf');        % NASA CDF patch (TT2000-aware)
```

| Toolkit | Location | On `MATLABPATH` |
|---|---|---|
| MICE mex gateway | `/opt/naif/mice/lib/mice.mexa64` | `/opt/naif/mice/lib` |
| MICE `cspice_*` wrappers | `/opt/naif/mice/src/mice/` | `/opt/naif/mice/src/mice` |
| NASA CDF patch | `/opt/cdf/matlab_cdf_patch/` | `/opt/cdf/matlab_cdf_patch` |

### Python with uv

`uv` and `uvx` are on `PATH`. `uv` can install standalone Python versions and
packages on its own (it does not rely on a system Python or system `tar`):

```bash
docker run --rm --entrypoint uv ghcr.io/alastairtree/not-so-fat-lab:latest \
  python install 3.13
```

---

## Build

Build context is this folder:

```bash
docker build -t not-so-fat-lab ./not-so-fat-lab
```

### Build arguments

| Arg | Default | Purpose |
|---|---|---|
| `MATLAB_RELEASE` | `R2026a` | MATLAB release passed to `mpm --release` |
| `ADDITIONAL_PRODUCTS` | the 8 toolboxes below | space-separated `mpm` product names installed on top of MATLAB |
| `BUILD_IMAGE` | `registry.access.redhat.com/ubi8/ubi:latest` | throwaway installer-stage base |
| `RUNTIME_IMAGE` | `registry.access.redhat.com/ubi8/ubi-minimal:latest` | final runtime base |
| `UV_IMAGE` | `ghcr.io/astral-sh/uv:latest` | image `uv`/`uvx` are copied from |

Default `ADDITIONAL_PRODUCTS`:

```
Statistics_and_Machine_Learning_Toolbox Signal_Processing_Toolbox
Curve_Fitting_Toolbox Optimization_Toolbox MATLAB_Report_Generator
Control_System_Toolbox Mapping_Toolbox Communications_Toolbox
```

Override, e.g. for a leaner image:

```bash
docker build -t not-so-fat-lab \
  --build-arg ADDITIONAL_PRODUCTS="Signal_Processing_Toolbox Optimization_Toolbox" \
  ./not-so-fat-lab
```

Building requires **no MATLAB licence**: `mpm` only downloads and installs the
product files. A licence is checked out only when MATLAB actually runs.

---

## Image sizes

Measured on this build (`linux/amd64`, R2026a). *Compressed* is the registry /
`docker pull` size; *on disk* is the unpacked size shown by `docker images`.

### Head-to-head: the same MATLAB, batch vs. the stock image

Both images below contain **MATLAB R2026a with no add-on toolboxes**.
`not-so-fat-lab` additionally bundles `uv` + NASA MICE + NASA CDF, which the
stock image does **not** — and is still substantially smaller:

| Image | Compressed (pull) | On disk |
|---|---:|---:|
| `mathworks/matlab:r2026a` (stock: MATLAB + desktop / matlab-proxy stack) | 2.79 GB | 10.4 GB |
| **`not-so-fat-lab`** (MATLAB, batch-only, **+ uv + MICE + CDF**) | **2.01 GB** | **7.39 GB** |
| **Saving** | **−0.78 GB (−28%)** | **−3.0 GB (−29%)** |

### Where the base saving comes from

| Layer | Compressed | On disk |
|---|---:|---:|
| `ubi8-minimal` (our base) | 0.04 GB | 0.14 GB |
| `mathworks/matlab-deps:r2026a` (stock dependency base) | 0.31 GB | 1.35 GB |
| `not-so-fat-lab` runtime base (pruned deps + uv + MICE + CDF, no MATLAB) | 0.15 GB | 0.63 GB |

The bundled extras are cheap (on disk): NASA MICE ~22 MB (trimmed from the
137 MB tarball to just the runtime mex + `.m` wrappers), NASA CDF 18 MB,
`uv` 61 MB.

### With the default toolboxes (what CI builds)

The default `ADDITIONAL_PRODUCTS` requests 8 toolboxes; `mpm` also pulls in DSP
System Toolbox (a hard dependency of Communications Toolbox), for 9 in total.
This is the image most people will actually run, measured on disk
(`docker images`, `linux/amd64`, R2026a Update 3):

| Build | On disk |
|---|---:|
| default toolboxes, before any MATLAB-payload pruning | 9.92 GB |
| **default toolboxes, after pruning** (the shipped image) | **8.5 GB** |
| **saving from pruning** | **−1.4 GB (−14%)** |

The ~730 MB carved out of the MATLAB install (see
[What's stripped out](#whats-stripped-out-and-why)) plus the ~115 MB MICE trim
account for the difference; the toolbox bytes themselves are unchanged. Trimming
`ADDITIONAL_PRODUCTS` to only the toolboxes you need is the largest remaining
lever — the 9 toolboxes are ~1.9 GB on their own.

The MATLAB-only head-to-head above is kept because it isolates the *structural*
saving (minimal base + pruned deps + multi-stage tooling removal) apples-to-
apples against the stock image; the pruning saving here stacks on top of it.

### How this was validated

Validated **end-to-end against a real network licence server** (FlexLM,
`port@host` via `MLM_LICENSE_FILE`), running the shipped image with its default
entrypoint as the non-root `matlab` user — i.e. exactly how a downstream job
runs it:

* `mpm` installs MATLAB R2026a; the launcher works (`matlab -help`, `matlab -n`).
* `docker run -e MLM_LICENSE_FILE=… <image> -batch "…"` **checks out a licence
  and executes**: `version` → `R2026a Update 3`, arithmetic returns, exit code 0.
* **MICE** loads and computes inside that licensed session:
  `cspice_tkvrsn('TOOLKIT')` → `CSPICE_N0067`, `mice.mexa64` resolves on
  `MATLABPATH`, and `cspice_convrt(1,'AU','KM')` returns 149 597 870.614.
* The **NASA CDF** patch (`spdfcdfinfo` / `spdfcdfread`) resolves on `MATLABPATH`,
  and `uv` is on `PATH`.

> **Note — `mesa-libgbm` is required.** The R2026a engine `dlopen`s
> `libgbm.so.1` during start-up (it is *not* a linked dependency, so `ldd`
> does not reveal it). If it is missing, `matlab -batch` dies **silently with
> exit 127 before printing anything**. It is therefore pinned in
> `base-dependencies.txt`; do not drop it when pruning further.

---

## Continuous integration

The workflow ships at [`ci/not-so-fat-lab.yml`](ci/not-so-fat-lab.yml). GitHub
only runs workflows from `.github/workflows/`, so copy it there once to activate
it (see [`ci/README.md`](ci/README.md) — it lives here rather than pre-installed
because the generating session's git token lacked the `workflow` OAuth scope):

```bash
mkdir -p .github/workflows
cp not-so-fat-lab/ci/not-so-fat-lab.yml .github/workflows/
git add .github/workflows/not-so-fat-lab.yml && git commit -m "Activate CI" && git push
```

What it does:

* **Monthly** (`cron: 0 3 1 * *`) and **on demand** (`workflow_dispatch`): free
  up runner disk, build the full image, smoke-test it, and push to GHCR
  (`ghcr.io/<owner>/not-so-fat-lab`) tagged `latest`, `r2026a`, and
  `r2026a-<date>`. The monthly rebuild keeps the base current with OS security
  updates and the latest `uv` / MICE / CDF releases.
* **On push / PR** touching the image files: a fast `hadolint` lint only — the
  full MATLAB build pulls many GB, so it does not run on every commit.

The build step needs no secrets (mpm install needs no licence). If you add an
`MLM_LICENSE_FILE` repository secret pointing at a licence server reachable from
the runner, CI additionally runs a real `matlab -batch` smoke test that asserts
MICE and the CDF patch are reachable.

---

## Design notes & limitations

* **Batch only, never a UI.** The dependency set is the minimal one MATLAB
  `dlopen`s to start headless. Functions that render figures may need extra
  libraries (e.g. `Xvfb`); add them in a downstream layer if required.
* **Non-root by default.** Runs as user `matlab` (uid 1000). Switch to
  `USER root` in a downstream stage if you need to install more.
* **Licence & redistribution.** The image contains MATLAB; keep published
  images access-controlled and observe your MathWorks licence terms. The GHCR
  package is private by default.
* **Base image choice.** UBI8 (RHEL 8 userland, glibc 2.28) is the smallest
  base MathWorks officially supports and what the NASA precompiled mex files
  are happy against. Any distro works — smaller is better — but UBI8-minimal is
  a good, supported sweet spot.

## References

* MathWorks reference Dockerfile — <https://github.com/mathworks-ref-arch/matlab-dockerfile>
* MathWorks `matlab-deps` (dependency lists per OS) — <https://github.com/mathworks-ref-arch/container-images>
* NASA NAIF MICE — <https://naif.jpl.nasa.gov/naif/toolkit_MATLAB.html>
* NASA CDF for MATLAB — <https://cdf.gsfc.nasa.gov/>
* uv — <https://docs.astral.sh/uv/>
