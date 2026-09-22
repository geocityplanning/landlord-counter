package com.agentos.companion;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Button;
import android.widget.Toast;

/**
 * 伴随应用入口 —— 就干一件事: 确保悬浮窗权限, 然后把悬浮球服务拉起来。
 *
 * 2026-09-22 用户要的形态:
 *   装**云手机里** ⇒ 球浮在棋牌界面上方 ✓ (云手机有 root ⇒ appops 直接授权 ✓ 不用用户点 ✓)
 *   用户手机端只是"显示器+遥控器" ⇒ 天然看到这个球 ✓
 *
 * ⚠ 本 App **只显示** ✗ —— 不点牌/不注入/不用无障碍(那才是能被识别的 ✗)
 */
public class MainActivity extends Activity {

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setBackgroundColor(Color.parseColor("#0E141F"));
        int pad = (int) (24 * getResources().getDisplayMetrics().density);
        root.setPadding(pad, pad, pad, pad);

        TextView tv = new TextView(this);
        tv.setText("伴随应用 · 悬浮球\n\n球会浮在棋牌界面上方,\n点球展开面板(记牌/牌池/推荐)。");
        tv.setTextColor(Color.parseColor("#EDF5FF"));
        tv.setTextSize(15);
        tv.setGravity(Gravity.CENTER);
        root.addView(tv, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        Button bt = new Button(this);
        bt.setText("启动悬浮球");
        // ⚠ 用匿名内部类而不是 lambda: 编译时 -bootclasspath 用 android.jar,
        //   没有 LambdaMetafactory ⇒ lambda 编译不过 ✗ (2026-09-22 踩过)
        bt.setOnClickListener(new android.view.View.OnClickListener() {
            @Override
            public void onClick(android.view.View v) {
                startOverlay();
            }
        });
        root.addView(bt);
        setContentView(root);

        startOverlay();          // 进来就自动拉起(云手机里免点 ✓)
    }

    private void startOverlay() {
        if (Build.VERSION.SDK_INT >= 23 && !Settings.canDrawOverlays(this)) {
            // 真机上走授权页; 云手机里我们直接用 appops 给 ✓ (这里只是兜底)
            try {
                startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:" + getPackageName())));
                Toast.makeText(this, "请允许'显示在其他应用上层'", Toast.LENGTH_LONG).show();
            } catch (Exception e) {
                Toast.makeText(this, "授权页打不开: " + e, Toast.LENGTH_LONG).show();
            }
        }
        try {
            startService(new Intent(this, OverlayService.class));
        } catch (Exception e) {
            Toast.makeText(this, "服务起不来: " + e, Toast.LENGTH_LONG).show();
        }
    }
}
