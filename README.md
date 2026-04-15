# SpaceHog CLI

A gorgeous disk space analyzer with a TUI interface.

## Install

```
curl -fsSL https://spacehog.nodehome.org/install.sh | sudo bash
```

## Requirements

- Ubuntu, Debian, Pop!_OS, or Mint
- `curl`, `gpg`, `apt` (usually pre-installed)

## Usage

After installing, run `spacehog` for the full-screen TUI scanner or `spacehog-tui` for the alternative TUI interface.

## Uninstall

```
sudo apt remove spacehog
sudo rm /etc/apt/sources.list.d/spacehog.list
sudo rm /etc/apt/trusted.gpg.d/spacehog.gpg
```

## License

MIT
