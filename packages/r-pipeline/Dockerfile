# syntax=docker/dockerfile:1

FROM r-base:4.4.1

ENV DEBIAN_FRONTEND=noninteractive \
    BITLYSIS_R_PKG_ROOT=/opt/bitlysis/packages/r-pipeline

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libcurl4-openssl-dev \
        libssl-dev \
        libxml2-dev \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/bitlysis/packages/r-pipeline
COPY packages/r-pipeline /opt/bitlysis/packages/r-pipeline

RUN Rscript tools/ci_install.R

# Smoke-check package load at build time.
RUN Rscript -e "source('R/bitlysis_run.R')"

# Runtime default for Render worker/cron override.
CMD ["Rscript", "inst/cli/run_analysis.R", "examples/req.json"]
