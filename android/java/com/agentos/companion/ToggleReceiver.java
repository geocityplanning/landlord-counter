package com.agentos.companion;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * 远程开关面板(2026-09-22 加)
 *
 * 为什么: 云手机容器把输入配成 `-touch`(无触摸屏 ✗) ⇒ 注入的点击**到不了悬浮窗** ✗
 *   ⇒ 容器里没法用手指点球 ⇒ 加一条命令通路, 我/壳子/脚本都能远程展收 ✓
 *
 * 用法: adb -s 127.0.0.1:5555 shell am broadcast -a com.agentos.companion.TOGGLE
 *       (真机上球照样能点 ✓ —— 这条只是给"点不到"的环境用 ✓)
 */
public class ToggleReceiver extends BroadcastReceiver {
    public static final String ACTION = "com.agentos.companion.TOGGLE";

    @Override
    public void onReceive(Context ctx, Intent it) {
        if (!ACTION.equals(it.getAction())) {
            return;
        }
        Intent s = new Intent(ctx, OverlayService.class);
        s.setAction(ACTION);
        try {
            ctx.startService(s);
        } catch (Exception ignored) {
        }
    }
}
