FROM debian:bookworm@sha256:854dd8ab51d62866dbd8f5431d15ce77b12983a2a4a1e1fe43a2395dc7ef9f61
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends openems octave-openems octave python3-numpy python3-h5py && rm -rf /var/lib/apt/lists/*
WORKDIR /work
CMD ["octave", "--no-gui", "--quiet", "simulations/generate_patch.m"]
