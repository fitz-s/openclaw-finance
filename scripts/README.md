# scripts

## sync_gstack_plan.sh
解决 `/office-hours` + Claude Code plan mode 的 stale file 问题。

### 用法
```bash
bash scripts/sync_gstack_plan.sh .gstack/projects/myproj/design.md
```

---

## build_handoff_zip.py
把当前仓库里的文档和 guidance 打成一个 handoff zip。

### 用法
```bash
python scripts/build_handoff_zip.py --project-name my-project --include-src
```
