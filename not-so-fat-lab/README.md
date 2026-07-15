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
| **Multi-stage build** | `mpm`, `curl`, `tar`/`unzip`, package-manager caches and install logs stay in the throwaway *installer* stage and never reach the shipped image |
| **No desktop / proxy stack** | unlike `mathworks/matlab`, there is no VNC, no `matlab-proxy`, no Xvfb, no supervisor |

The MATLAB product bits themselves are the same either way, so the savings come
from the base OS, the dependency diet, and leaving all build tooling behind.

See [Image sizes](#image-sizes) for measured numbers.

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

The bundled extras are cheap (on disk): NASA MICE 137 MB, NASA CDF 18 MB,
`uv` 61 MB.

### With the 8 default toolboxes (what CI builds)

The default `ADDITIONAL_PRODUCTS` adds 8 toolboxes. Toolbox bytes are identical
wherever they are installed, so they raise this image and any stock-based
equivalent by the *same* amount — the ~28% structural saving above (minimal
base + pruned deps + multi-stage tooling removal + no desktop/proxy stack)
carries straight over. The MATLAB-only figures are quoted here because they
isolate that saving apples-to-apples and keep the measurement build fast.

### How this was validated

Building needs no licence, and running MATLAB code does — so batch execution
can't be exercised end-to-end here. Instead the image was validated up to the
licence boundary, and behaviourally against the stock image:

* `mpm` installs MATLAB R2026a; the launcher works (`matlab -help`, `matlab -n`).
* `ldd` on the main MATLAB binary reports **no missing libraries**; MATLAB
  starts far enough to initialise its preferences directory.
* `matlab -batch` then stops at **licence checkout** — the *same* outcome class
  as `mathworks/matlab:r2026a`, which (being wired for MathWorks online
  licensing) instead prompts for an account e-mail. Neither fails on libraries;
  both simply need a licence. This confirms the pruned, batch-only dependency
  set is sufficient for MATLAB start-up.
* `uv`, MICE (`mice.mexa64` + `cspice_*`) and the CDF patch (`spdfcdfread`) are
  all present and on `MATLABPATH` in the final image.

---

## Continuous integration

`.github/workflows/not-so-fat-lab.yml`:

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
