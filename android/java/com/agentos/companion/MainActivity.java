package com.agentos.companion;

import android.app.Activity;
import android.os.Bundle;
import android.view.ViewGroup;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

/**
 * 伴随应用入口 —— 全屏加载**离线**棋牌 demo。
 *
 * 2026-09-22 改版(用户拍板"统一打包"):
 *   以前这个入口是"拉起悬浮球服务"(Android 悬浮窗 ✓), 现在改成**全屏 WebView** 加载
 *   `file:///android_asset/game/demo.html` —— 游戏 + 🃏悬浮球 + 记牌器 + 出牌推荐 + AI托管
 *   **全在页面里** ⇒ 一套前端两种形态(网页/APK 同一份源码 ✓)
 *
 * 为什么不用 Android 悬浮窗这套:
 *   · 云手机容器把输入配成 `-touch`(无触摸屏) ⇒ 注入点击到不了叠加窗 ✗ 球拖不动点不开 ✗
 *   · 页面内元素没这个问题 ✓ 且真机上也一样能用 ✓ (少一层系统权限 ✓)
 *
 * 为什么能离线:
 *   游戏资源全部打进 APK 的 assets ✓ 决策用游戏自带 AI(纯 JS ✓)
 *   ⇒ **不联网、不用服务器、不算力** ✓ 飞行模式可玩 ✓
 *
 * 输出:
 *   android/build/companion.apk   (debug 签名 ⇒ 直接装真机试用 ✓)
 */
public class MainActivity extends Activity {

    private WebView web;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);                    // 游戏的设置(级牌)要存 localStorage
        s.setAllowFileAccess(true);
        s.setAllowFileAccessFromFileURLs(true);          // file:// 下加载同目录 js ✓
        s.setAllowUniversalAccessFromFileURLs(true);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setMediaPlaybackRequiresUserGesture(false);
        web.setBackgroundColor(0xFF0E141F);
        // 站内跳转不出 WebView ✓ (匿名内部类 —— 本工程 javac 用 android.jar 当 bootclasspath,
        //  没有 LambdaMetafactory ⇒ lambda 编译不过 ✗ 2026-09-22 踩过)
        web.setWebViewClient(new WebViewClient());

        FrameLayout root = new FrameLayout(this);
        root.addView(web, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);

        web.loadUrl("file:///android_asset/game/index.html");   // 等新界面定了再指过去(2026-09-22)
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
            return;
        }
        super.onBackPressed();
    }
}
