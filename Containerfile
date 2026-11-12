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
# Debian packages are fetched only over verified HTTPS, so builds need no outbound
# port 80. The slim base has no ca-certificates, so the pinned base's Node.js root
# certificates verify the fetches until Debian ca-certificates is installed. With
# host CA trust enabled, the selected bundle arrives as the optional build-ca
# secret (never stored in a layer) and is appended for TLS-intercepting networks.
# The temporary bundle stays readable by apt's _apt user and is removed in this step.
RUN --mount=type=secret,id=build-ca,required=false \
    node -e 'process.stdout.write(require("tls").rootCertificates.join("\n") + "\n")' \
        > /tmp/apt-bootstrap-ca.pem \
    && if [ -s /run/secrets/build-ca ]; then cat /run/secrets/build-ca >> /tmp/apt-bootstrap-ca.pem; fi \
    && sed -i 's|^URIs: http://|URIs: https://|' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::https::CAInfo=/tmp/apt-bootstrap-ca.pem update \
    && apt-get -o Acquire::https::CAInfo=/tmp/apt-bootstrap-ca.pem install --no-install-recommends -y \
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
    && rm -f /tmp/apt-bootstrap-ca.pem \
    && npm install --global --omit=dev \
        "@fission-ai/openspec@${OPENSPEC_VERSION}" \
        "opencode-ai@${OPENCODE_VERSION}" \
    && test "$(opencode --version)" = "$OPENCODE_VERSION" \
    && test "$(openspec --version)" = "$OPENSPEC_VERSION" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /root/.npm /root/.cache /opencode-home \
    && mkdir -m 1777 /opencode-home \
    && mkdir -p /workspace

# Agent-side relay for restricted sessions; the guard is mounted from the
# protected installation at launch, never baked into this image.
COPY network/relay.py network/mux.py /opt/sandbox-egress/

# /workspace is created in the package step above: a WORKDIR missing from every
# layer is created and chowned by the engine at each container start, which
# fails for large domain UIDs under --userns=keep-id.
WORKDIR /workspace
ENTRYPOINT ["opencode"]
