FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates wget gnupg \
 && wget -qO- https://apt.llvm.org/llvm-snapshot.gpg.key | gpg --dearmor -o /usr/share/keyrings/llvm.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/llvm.gpg] http://apt.llvm.org/noble/ llvm-toolchain-noble-21 main" > /etc/apt/sources.list.d/llvm.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends clang-21 libclang-rt-21-dev llvm-21 libstdc++-13-dev \
 && ln -s /usr/bin/llvm-symbolizer-21 /usr/local/bin/llvm-symbolizer \
 && apt-get purge -y wget gnupg && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home runner
USER runner
WORKDIR /work
