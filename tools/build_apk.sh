#!/usr/bin/env bash
# 打"伴随应用"悬浮球 APK —— 故意不用 Gradle ✓ (少依赖、少下载、一条命令可复现 ✓)
#
# 用法: bash tools/build_apk.sh
# 产出: android/build/companion.apk   (debug 签名 ⇒ 装机器/云手机试用够用 ✓)
#
# 依赖(已就位 ✓): JDK 17 · /opt/android-sdk/build-tools/34.0.0 · platforms/android-34
set -euo pipefail

SDK=${ANDROID_SDK_ROOT:-/opt/android-sdk}
BT="$SDK/build-tools/34.0.0"
PLAT="$SDK/platforms/android-34/android.jar"
SRC="$(cd "$(dirname "$0")/.." && pwd)/android"
REPO="$(cd "$SRC/.." && pwd)"
OUT="$SRC/build"
PY=/usr/local/lib/hermes-agent/venv/bin/python3

for f in "$BT/aapt2" "$BT/d8" "$BT/apksigner" "$BT/zipalign" "$PLAT"; do
  [ -e "$f" ] || { echo "✗ 缺 $f (先装 Android SDK ✓)"; exit 1; }
done

rm -rf "$OUT"; mkdir -p "$OUT/gen" "$OUT/classes" "$OUT/dex" "$OUT/assets"

# ⓪ 游戏资源: **打包时**从唯一源码拷进 build 临时目录 ✓
#    ⚠ 不落仓库(android/assets/ 已 gitignore 且已删 ✗) —— 靠人记着拷迟早对不上
#      (2026-09-22 实测: assets 里那份还是 demo 之前的旧拷贝 ⇒ 打出来的包没有记牌器 ✗)
GAME_SRC="$REPO/lab/guandan_www"
[ -d "$GAME_SRC" ] || { echo "✗ 找不到游戏源码 $GAME_SRC"; exit 1; }
echo "⓪ 拷游戏(lab/guandan_www → build/assets/game)"
cp -r "$GAME_SRC/." "$OUT/assets/game/"
echo "   $(find "$OUT/assets/game" -type f | wc -l) 个文件 $(du -sh "$OUT/assets/game" | cut -f1)"
[ -f "$OUT/assets/game/js/demo.js" ] || { echo "✗ 缺 js/demo.js(伴随前端) ⇒ 拒绝打包 ✗"; exit 1; }

echo "① 编译资源"
"$BT/aapt2" compile --dir "$SRC/res" -o "$OUT/res.zip"

echo "② 链接资源+清单(生成 R.java)"
# ⚠ 编译产物要当**位置参数**给 aapt2 ✓ (写成 -R 会被当成"覆盖包" ⇒
#   "resource ... does not override an existing resource" ✗ 2026-09-22 踩过)
"$BT/aapt2" link -o "$OUT/base.apk" -I "$PLAT" --manifest "$SRC/AndroidManifest.xml" \
    "$OUT/res.zip" -A "$OUT/assets" --java "$OUT/gen" --min-sdk-version 26 --target-sdk-version 28

echo "③ javac"
javac -source 8 -target 8 -nowarn -bootclasspath "$PLAT" -classpath "$PLAT" \
    -d "$OUT/classes" $(find "$SRC/java" "$OUT/gen" -name '*.java')

echo "④ d8 → dex"
"$BT/d8" --lib "$PLAT" --min-api 26 --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')

echo "⑤ 把 dex 放进 APK(必须在根目录 ✓)"
cp "$OUT/base.apk" "$OUT/app.apk"
"$PY" - "$OUT/app.apk" "$OUT/dex/classes.dex" <<'PYEOF'
import sys, zipfile
apk, dex = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(apk, 'a', zipfile.ZIP_DEFLATED) as z:
    z.write(dex, 'classes.dex')
print("   + classes.dex", __import__('os').path.getsize(dex), "字节")
PYEOF

echo "⑥ 对齐 + 签名(debug keystore ✓ 试用够用)"
"$BT/zipalign" -f 4 "$OUT/app.apk" "$OUT/app-aligned.apk"
# ⚠ keystore 必须放在 build 目录**外面** ✗ —— 放里面每次 rm -rf 就重生成一把新钥匙
#   ⇒ 覆盖安装报 INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures do not match ✗ (2026-09-22 踩过)
KS="$SRC/debug.keystore"
if [ ! -f "$KS" ]; then
  keytool -genkeypair -keystore "$KS" -alias a -storepass android \
      -keypass android -keyalg RSA -keysize 2048 -validity 10000 \
      -dname "CN=Companion, O=AgentOS" >/dev/null 2>&1
fi
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:android --key-pass pass:android \
    --out "$OUT/companion.apk" "$OUT/app-aligned.apk"
"$BT/apksigner" verify "$OUT/companion.apk" && echo "   ✓ 签名校验通过"
"$BT/aapt2" dump badging "$OUT/companion.apk" 2>/dev/null | head -3 || true
ls -la "$OUT/companion.apk"
