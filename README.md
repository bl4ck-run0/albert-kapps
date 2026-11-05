# albert-kapps

> [!WARNING]
> This is a one-off personal plugin that was **vibecoded**. It is:
>
> - **not maintained**
> - **not guaranteed correct or complete** (no localized names, minimal desktop-entry support, best-effort Exec field expansion)
> - provided with **no support whatsoever**
>
> Use at your own risk. Issues and pull requests may be ignored.

KRunner-style application launcher plugin for Albert.

Albert's built in application search was too strict. I was used to `krunner` so I wanted its style of search. Thus, this plugin.

- substring match → strongest
- prefix-of-word → strong
- loose subsequence (across letters/words) → fallback

## Install

1. Copy `kapps.py` into `~/.local/share/albert/python/plugins/`
2. Enable the **Python plugins** plugin in Albert's settings
3. Restart Albert

## Self-check

```sh
python3 kapps.py
```

## License

MIT. See `LICENSE`.
