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
OUT="$SRC/build"
PY=/usr/local/lib/hermes-agent/venv/bin/python3

for f in "$BT/aapt2" "$BT/d8" "$BT/apksigner" "$BT/zipalign" "$PLAT"; do
  [ -e "$f" ] || { echo "✗ 缺 $f (先装 Android SDK ✓)"; exit 1; }
done

rm -rf "$OUT"; mkdir -p "$OUT/gen" "$OUT/classes" "$OUT/dex"

echo "① 编译资源"
"$BT/aapt2" compile --dir "$SRC/res" -o "$OUT/res.zip"

echo "② 链接资源+清单(生成 R.java)"
# ⚠ 编译产物要当**位置参数**给 aapt2 ✓ (写成 -R 会被当成"覆盖包" ⇒
#   "resource ... does not override an existing resource" ✗ 2026-09-22 踩过)
"$BT/aapt2" link -o "$OUT/base.apk" -I "$PLAT" --manifest "$SRC/AndroidManifest.xml" \
    "$OUT/res.zip" --java "$OUT/gen" --min-sdk-version 26 --target-sdk-version 28

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
