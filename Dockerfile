ARG OPENCODE_VERSION=1.18.3

FROM ghcr.io/anomalyco/opencode:${OPENCODE_VERSION}

ARG USER_NAME=opencode
ARG USER_ID=1000
ARG GROUP_ID=1000

RUN apk add --no-cache \
        bash \
        ca-certificates \
        curl \
        git \
        jq \
        podman-remote \
        ripgrep \
    && addgroup -g "${GROUP_ID}" "${USER_NAME}" \
    && adduser -D -h "/home/${USER_NAME}" -s /bin/bash -u "${USER_ID}" -G "${USER_NAME}" "${USER_NAME}" \
    && ln -s /usr/bin/podman-remote /usr/local/bin/podman

COPY opencode-entrypoint /usr/local/bin/opencode-entrypoint
RUN chmod 0755 /usr/local/bin/opencode-entrypoint

USER ${USER_ID}:${GROUP_ID}
WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/opencode-entrypoint"]
