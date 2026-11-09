# Image inputs are pinned. Update them only through the maintenance procedure in
# README.md ("Updating pinned image inputs") and record the result in docs/validation.md.
FROM docker.io/library/node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da

ARG OPENCODE_VERSION=1.18.3
ARG OPENSPEC_VERSION=1.16.0

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/opencode-home \
    OPENCODE_DISABLE_AUTOUPDATE=1

# npm verifies the registry integrity of every package; the platform binary
# packages are exact-version optional dependencies of opencode-ai.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        bash \
        bubblewrap \
        bzip2 \
        ca-certificates \
        coreutils \
        curl \
        diffutils \
        file \
        findutils \
        gawk \
        git \
        grep \
        jq \
        less \
        nano \
        patch \
        podman \
        procps \
        python3 \
        ripgrep \
        sed \
        tar \
        unzip \
        util-linux \
        xz-utils \
        zip \
    && npm install --global --omit=dev \
        "@fission-ai/openspec@${OPENSPEC_VERSION}" \
        "opencode-ai@${OPENCODE_VERSION}" \
    && test "$(opencode --version)" = "$OPENCODE_VERSION" \
    && test "$(openspec --version)" = "$OPENSPEC_VERSION" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /root/.npm /root/.cache /opencode-home \
    && mkdir -m 1777 /opencode-home

WORKDIR /workspace
ENTRYPOINT ["opencode"]
