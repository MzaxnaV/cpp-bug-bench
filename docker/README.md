# docker/

The grading image: Ubuntu 24.04 and clang 21 with sanitizers.
```bash
docker build -t cbb-grader docker/
```

## NOTES

TSan needs certain address ranges to be free. Newer Linux kernels randomize across a wider range (vm.mmap_rnd_bits = 32), and on these kernels the program sometimes lands where TSan needs to be and when TSan detects this, it restarts the program once with ASLR turned off (using `personality(ADDR_NO_RANDOMIZE)`). Docker's default profile blocks it. Details here: [moby/moby#43011](https://github.com/moby/moby/issues/43011). 

So there's a custom Docker's [default seccomp profile](https://github.com/moby/profiles/blob/main/seccomp/default.json) that  allows `personality(ADDR_NO_RANDOMIZE)` (value `262144`).


Run grading containers with:

```bash
docker run --security-opt seccomp=docker/seccomp.json ...
```

The image runs as user `runner`, so the folder mounted at `/src` must be readable by everyone (`chmod 755`).
