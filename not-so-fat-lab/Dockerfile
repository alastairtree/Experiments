# syntax=docker/dockerfile:1
#
# not-so-fat-lab
# ==============
# A deliberately slim, **batch-only** MATLAB base image.
#
# Design goals (see README.md for the full rationale):
#   * Much smaller than the stock `mathworks/matlab` images, which ship the
#     whole interactive desktop / matlab-proxy / VNC stack we never use.
#   * Runs `matlab -batch` headlessly. It will NEVER run a UI.
#   * Ships the requested toolboxes (configurable via ADDITIONAL_PRODUCTS),
#     the NASA NAIF SPICE toolkit for MATLAB (MICE) and the NASA CDF patch,
#     and the `uv` Python manager -- and nothing else.
#   * A multi-stage build so that mpm, wget/curl, tar, and the package
#     manager caches used to assemble the image are left behind in the
#     builder and never bloat the runtime image.
#
# UBI8 is the smallest base officially supported by MATLAB, so we start there
# and use ubi8-minimal (microdnf) for the runtime stage to shave the OS layer.

ARG MATLAB_RELEASE=R2026a

# Full UBI8 for the builder (throwaway) -- it already carries the shell tooling
# mpm expects (tar/gzip/unzip). Minimal UBI8 for the runtime image.
ARG BUILD_IMAGE=registry.access.redhat.com/ubi8/ubi:latest
ARG RUNTIME_IMAGE=registry.access.redhat.com/ubi8/ubi-minimal:latest

# uv is copied straight out of the official distroless image -- no installer,
# no curl-pipe-sh, nothing to clean up afterwards.
ARG UV_IMAGE=ghcr.io/astral-sh/uv:latest


##############################################################################
# uv source stage. A dedicated stage is required because `COPY --from=` cannot
# expand a build ARG directly; it can reference a stage name that was built
# from one.
##############################################################################
FROM ${UV_IMAGE} AS uv


##############################################################################
# Stage 1 -- installer
#
# Everything heavy and single-use lives here: mpm, the product downloads, the
# NASA tarballs and the tools to unpack them. The runtime stage copies only the
# finished /opt trees, so none of this tooling reaches the shipped image.
##############################################################################
FROM ${BUILD_IMAGE} AS installer

ARG MATLAB_RELEASE

# Products baked into the image. Override at build time, e.g.:
#   --build-arg ADDITIONAL_PRODUCTS="Signal_Processing_Toolbox Optimization_Toolbox"
# MATLAB itself is always installed; these are added on top.
ARG ADDITIONAL_PRODUCTS="Statistics_and_Machine_Learning_Toolbox Signal_Processing_Toolbox Curve_Fitting_Toolbox Optimization_Toolbox MATLAB_Report_Generator Control_System_Toolbox Mapping_Toolbox Communications_Toolbox"

# Tooling used ONLY to fetch/unpack, plus mpm's own runtime deps (libatomic).
# All of this stays in this throwaway stage; none reaches the runtime image.
RUN yum install -y --setopt=install_weak_deps=False --setopt=tsflags=nodocs \
        tar gzip unzip ca-certificates libatomic \
    && yum clean all

# --- MATLAB via MATLAB Package Manager (mpm) -------------------------------
# mpm installs the product bits. No licence is required to *install* MATLAB;
# a licence is only needed to *run* it (supplied at container runtime).
WORKDIR /tmp/mpm
RUN curl -fsSL -o mpm https://www.mathworks.com/mpm/glnxa64/mpm \
    && chmod +x mpm \
    && ./mpm install \
        --release=${MATLAB_RELEASE} \
        --destination=/opt/matlab/${MATLAB_RELEASE} \
        --products MATLAB ${ADDITIONAL_PRODUCTS} \
    || { echo "==== mpm install failed; /tmp/mathworks_root.log follows ===="; \
         cat /tmp/mathworks_root.log 2>/dev/null; exit 1; }

# --- NASA NAIF SPICE toolkit for MATLAB (MICE) -----------------------------
# Precompiled glnxa64 mex files -- no compiler needed.
# https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/MATLAB/req/mice.html
RUN mkdir -p /opt/naif && cd /opt/naif \
    && curl -fsSL -o mice.tar.Z \
        https://naif.jpl.nasa.gov/pub/naif/toolkit/MATLAB/PC_Linux_GCC_MATLAB9.x_64bit/packages/mice.tar.Z \
    && gzip -d mice.tar.Z \
    && tar xf mice.tar \
    && rm -f mice.tar

# --- NASA CDF (Common Data Format) MATLAB patch ----------------------------
# Precompiled glnxa64 -- no compiler needed. https://cdf.gsfc.nasa.gov/
# "latest_matlab" tracks the current release; rename to a stable path so the
# MATLABPATH below need not track the embedded version number.
RUN mkdir -p /opt/cdf && cd /opt/cdf \
    && curl -fsSL -o matlab_cdf_lin64.tar.gz \
        https://spdf.gsfc.nasa.gov/pub/software/cdf/dist/latest_matlab/matlab_cdf_lin64.tar.gz \
    && tar xzf matlab_cdf_lin64.tar.gz \
    && rm -f matlab_cdf_lin64.tar.gz \
    && mv matlab_cdf*_patch-64 matlab_cdf_patch


##############################################################################
# Stage 2 -- runtime
#
# Minimal UBI8. Only the shared libraries MATLAB dlopen()s to start in batch
# mode, plus uv. No mpm, no wget/curl, no build caches.
##############################################################################
FROM ${RUNTIME_IMAGE} AS runtime

ARG MATLAB_RELEASE

LABEL org.opencontainers.image.title="not-so-fat-lab" \
      org.opencontainers.image.description="Slim batch-only MATLAB ${MATLAB_RELEASE} base image (UBI8) with NASA MICE + CDF and uv." \
      org.opencontainers.image.source="https://github.com/alastairtree/experiments" \
      com.mathworks.matlab.release="${MATLAB_RELEASE}"

# Runtime shared libraries for MATLAB batch. This is the pruned, batch-only
# subset (see base-dependencies.txt) -- NOT the full desktop dependency set
# from matlab-deps, which is where a lot of the image size otherwise goes.
COPY base-dependencies.txt /tmp/base-dependencies.txt
RUN microdnf install -y --nodocs --setopt=install_weak_deps=0 \
        $(cat /tmp/base-dependencies.txt) \
    && microdnf clean all \
    && rm -rf /tmp/base-dependencies.txt /var/cache/yum /var/cache/dnf

# uv: Python package + Python-version manager, on PATH for downstream layers.
# Copied from the official distroless image -- no installer left behind.
COPY --from=uv /uv /uvx /usr/local/bin/

# UTF-8 locale + a machine-id (MATLAB expects one) without pulling in dbus.
ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8
RUN tr -d '-' < /proc/sys/kernel/random/uuid > /etc/machine-id \
    && mkdir -p /usr/share/X11/xkb

# Bring the finished trees across from the installer stage.
COPY --from=installer /opt/matlab /opt/matlab
COPY --from=installer /opt/naif   /opt/naif
COPY --from=installer /opt/cdf    /opt/cdf

# matlab on PATH; MATLABPATH makes MATLAB auto-add MICE + CDF to its search
# path at startup, regardless of the current working directory.
ENV PATH="/opt/matlab/${MATLAB_RELEASE}/bin:/usr/local/bin:${PATH}" \
    MATLABPATH="/opt/naif/mice/lib:/opt/naif/mice/src/mice:/opt/cdf/matlab_cdf_patch"

# Usage telemetry tags, mirroring the MathWorks reference images.
ENV MW_DDUX_FORCE_ENABLE=true \
    MW_CONTEXT_TAGS=MATLAB:DOCKERFILE:V1

# Run as an unprivileged user by default (downstream can `USER root` to extend).
RUN groupadd -g 1000 matlab \
    && useradd -u 1000 -g 1000 -m -d /home/matlab -s /bin/bash matlab
USER matlab
WORKDIR /home/matlab

# A licence is supplied at runtime, e.g.:
#   docker run -e MLM_LICENSE_FILE=27000@license.example.com <image> -batch "ver"
ENTRYPOINT ["matlab"]
CMD ["-help"]
