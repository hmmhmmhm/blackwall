FROM debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc
RUN apt-get update && apt-get install -y --no-install-recommends libicu72 libstdc++6 zlib1g ca-certificates && rm -rf /var/lib/apt/lists/*
COPY renode-1.17.0.linux-arm64-portable.tar.gz /tmp/renode.tar.gz
RUN echo "e9051578411441bfb47b77de0381cfba3badce03663367fab561472fd7807f1f  /tmp/renode.tar.gz" | sha256sum --check -
RUN mkdir /opt/renode && tar -xzf /tmp/renode.tar.gz -C /opt/renode --strip-components=1 && rm /tmp/renode.tar.gz
WORKDIR /opt/renode
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1
ENTRYPOINT ["/opt/renode/renode"]
