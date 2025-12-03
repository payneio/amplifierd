# Amplifier Education

This is a repo where I figure out what this amplifier thing is.

I started by using amplifier.v1 to create a set of documents about itself and put them in the [`guides`](./guides/README.md) folder.

Then I had amplifier create a set of notebooks that demonstrate how to use amplifier-core in the [`notebooks/amplifier-core`](./notebooks/amplifier-core/README.md) folder.

Then, I had amplifier create a web-server (daemon) to work with the amplifier-core packages in the [`amplifierd`](./amplifierd/README.md) folder, and a set of notebooks that demonstrate how to use that server in the [`notebooks/amplifierd`](./notebooks/amplifierd/README.md) folder. Run the daemon and then open the notebooks to see how to interact with it.

Now, I'm making a [webapp](./webapp/README.md) that works with the amplifierd server to try out some UI ideas.

This has grown more ambitious, though, wrapping in ideas I've been noodling over awhile about what an "[intelligent computation platform](./amplifierd/docs/the-amplifier-computation-platform.md)" might look like.

To get a better handle on amplifier@next (v2), feel free to explore the guides and notebooks.

## Quick start

```bash
# Clone the repo
mkdir <somewhere>
cd <somewhere>
git clone https://github.com/payneio/amplifierd.git

# Initial setup
make install

# Run the daemon
make daemon-dev

# Run the webapp dev server in another terminal
make webapp-dev
```

Now visit http://localhost:5174 in your browser.

A directory named `.amplifierd` will be created wherever you run the daeomon from. You can see some config in `.amplifierd/config/daemon.yaml`. The important one is the `data_dir` which is the "data root" of amplifier. Amplifier will have all access there. By default, it's set to your home directory (~) but you might want to change it to somewhere else where you aren't worried about your data getting messed up (this is an experiment).

Restart the daemon after changing config.
