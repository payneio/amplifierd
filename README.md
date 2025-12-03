# Amplifier Education

This is a repo where I figure out what this amplifier thing is.

Things made here (in rough order of creation):

- [`guides`](./guides/README.md): Docs about Amplifier.v2 (created by Amplifier.v1).
- [`notebooks/amplifier-core`](./notebooks/amplifier-core/README.md): Notebooks demonstrating how to use amplifier-core.
- [`amplifierd`](./amplifierd/README.md): The amplifier daemon (web server) that exposes amplifier-core functionality over HTTP.
- [`notebooks/amplifierd`](./notebooks/amplifierd/README.md): Notebooks demonstrating how to use the amplifierd server.
- [`webapp`](./webapp/README.md): A React webapp that uses the amplifierd server.

This has grown more ambitious, though, wrapping in ideas I've been noodling over awhile about what an "[intelligent computation platform](./amplifierd/docs/the-amplifier-computation-platform.md)" might look like.

To get a better handle on amplifier@v2, feel free to explore the guides and notebooks, or run the daemon and webapp locally to poke around.

## Quick start

```bash
# Clone the repo.
mkdir <somewhere>
cd <somewhere>
git clone https://github.com/payneio/amplifierd.git

# Initial setup.
# Prerequisites: Python 3.10+, Node.js 16+, pnpm, make, uv.
make install

# Run the daemon.
make daemon-dev

# Run the webapp dev server in a separate terminal.
make webapp-dev
```

Now visit http://localhost:5174 in your browser.

A directory named `.amplifierd` will be created wherever you run the daemon from. You can see some config in `amplifierd/.amplifierd/config/daemon.yaml`. The important one is `data_dir` which is the path to the "data root" of amplifier. Amplifier will have all access there. By default, it's set to your home directory (~) but you might want to change it to somewhere else where you aren't worried about your data getting messed up (this is an experiment).

Restart the daemon after changing config.
