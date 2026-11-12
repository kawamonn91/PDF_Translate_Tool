# CI と自動マージ

## CI（`.github/workflows/ci.yml`）

PR（main 向け）と main への push のたびに、GitHub Actions のジョブ `build` が次を行う。

- `pip install -r requirements.txt pytest`（依存パッケージのセットアップ）
- `python -m pytest -q`（単体テストの実行）

環境は Windows Server 2025（`windows-2025`）上の Python 3.12。アクションはコミットの SHA で固定している（更新するときは SHA ごと書き換える）。

## main の保護と自動マージ

- main は `build` が通らないとマージできない（ブランチの保護。管理者は対象外にしてあり、緊急時は直接 push できる）
- リポジトリで自動マージを有効にし、マージしたブランチは自動で消える
- PR を作ったら、自動マージを予約する。`build` が通った時点でマージされ、失敗したらマージされない

```bash
gh pr create --base main --title "…" --body "…"
gh pr merge --auto --merge   # build が通ったらマージする（マージコミット）
```

CI が失敗したら、同じブランチに直して push すれば、もう一度 CI が走り、通ればそのままマージされる。

## CD（`.github/workflows/release.yml`、デスクトップ版）

`v1.2.3` の形のタグを push すると、ジョブ `release`（`windows-2025`）が次を行う（アプリに版の番号のファイルが無いので、タグがそのまま版になる）。

1. Python 3.14（ポータブル版に入れる埋め込みの Python と同じ版）で `.venv` を作り、`requirements.txt` を入れて単体テスト
2. `build_portable.ps1` でポータブル版を作る
3. ポータブル版の埋め込みの Python から、アプリと同梱したライブラリ（PyMuPDF・PySide6 など）が import できるかを確かめる
4. `PDF-JA-Translator-<版>-win64.zip` と `SHA256SUMS` を GitHub Releases に置く

手で動かす（`gh workflow run release.yml`）と、3 までを行ってリリースは作らない（CD の動作確認用）。Secrets は使わない。

Android 版は対象外（MuPDF のネイティブライブラリ `libmupdf_java.so` を Git に入れておらず、CI でもビルドしていないため）。

```bash
git switch main && git pull --ff-only
git tag v1.2.3 && git push origin v1.2.3
gh run watch "$(gh run list --workflow release.yml --limit 1 --json databaseId -q '.[0].databaseId')"
```
