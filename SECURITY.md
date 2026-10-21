# Security policy

SeedGrid Audit is designed not to execute checkpoint code. It treats checkpoints as opaque files and parses only bounded-size UTF-8 metrics JSON. It rejects path patterns that resolve outside the configured root directory. This is a convenience tool, not a security sandbox.

If you identify a vulnerability, please use the GitHub repository's private security-advisory flow after publication instead of publishing an exploit or private paths in an issue. There are no guarantees of response times for this new volunteer-maintained project.
