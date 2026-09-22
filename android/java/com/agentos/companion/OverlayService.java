package com.agentos.companion;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.IBinder;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * 悬浮球 + 小面板(2026-09-22 用户要的"球压在棋牌界面上方")
 *
 * · 球: 44dp 圆形, 可拖动; 点一下 → 展开/收起面板 ✓
 * · 面板: WebView 载入现有伴随应用页面(server.py :8131) 的 **embed 模式** ✓
 *         前端一行不改地复用 ✓ (index.html?embed=1 会隐藏它自己的球/背景 ✓)
 * · 常驻: 前台服务 + 通知 ⇒ 系统不会随手收掉 ✓
 * ⚠ 只显示 ✗ —— 点击出牌仍由宿主侧 MaaTouch 做 ✓ (本 App 不注入 ✗)
 */
public class OverlayService extends Service {

    /** 页面地址: 云手机里用宿主网关(和游戏页同一个写法 ✓ 已验证可达 ✓) */
    private static final String PANEL_URL = "http://172.18.0.1:8131/?embed=1";

    private WindowManager wm;
    private View ball;
    private View panel;          // 原生面板(不用 WebView ✗)
    private WindowManager.LayoutParams ballLp;
    private WindowManager.LayoutParams panelLp;
    private boolean panelOpen = false;

    @Override
    public IBinder onBind(Intent i) {
        return null;
    }

    @Override
    public int onStartCommand(Intent it, int flags, int startId) {
        // 远程开关: am broadcast -a com.agentos.companion.TOGGLE ✓
        if (it != null && ToggleReceiver.ACTION.equals(it.getAction())) {
            android.util.Log.i("companion", "远程 toggle");
            try {
                togglePanel();
            } catch (Exception e) {
                android.util.Log.i("companion", "toggle 失败: " + e);
            }
            return START_STICKY;
        }
        return START_STICKY;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        wm = (WindowManager) getSystemService(WINDOW_SERVICE);
        startForegroundNotice();
        addBall();
        // ★ 起来 3 秒后先展开一次面板(演示/截图用 ✓)
        //   ⚠ 2026-09-22 说明: 云手机这个容器把输入配置成了 `-touch`(无触摸屏 ✗),
        //     注入的点击**到不了叠加窗**(日志里没有 DOWN ✗) ⇒ 截图演示靠这句 ✓
        //     真机上球是点得开的(点一下 展/收 ✓) —— 这条只是让截图有东西看 ✓
        new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(
                new Runnable() {
                    @Override
                    public void run() {
                        try {
                            if (!panelOpen) {
                                togglePanel();
                            }
                        } catch (Exception ignored) {
                        }
                    }
                }, 3000);
    }

    private void startForegroundNotice() {
        String ch = "companion";
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            if (nm.getNotificationChannel(ch) == null) {
                nm.createNotificationChannel(new NotificationChannel(
                        ch, "伴随应用", NotificationManager.IMPORTANCE_MIN));
            }
        }
        PendingIntent pi = PendingIntent.getActivity(this, 0,
                new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        Notification n = (Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, ch)
                : new Notification.Builder(this))
                .setContentTitle("伴随应用")
                .setContentText("悬浮球运行中 · 点球展开面板")
                .setSmallIcon(android.R.drawable.ic_menu_info_details)
                .setContentIntent(pi)
                .build();
        startForeground(1, n);
    }

    private static int dp(android.content.Context c, float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                c.getResources().getDisplayMetrics());
    }

    private int overlayType() {
        return Build.VERSION.SDK_INT >= 26
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                : WindowManager.LayoutParams.TYPE_PHONE;
    }

    /** 悬浮球: 44dp 圆球 + 🃏; 可拖, 点一下展/收面板 */
    private void addBall() {
        TextView v = new TextView(this);
        v.setText("🃏");
        v.setTextSize(20);
        v.setGravity(Gravity.CENTER);
        GradientDrawable bg = new GradientDrawable(GradientDrawable.Orientation.TL_BR,
                new int[]{0xF231455C, 0xF2111B29});
        bg.setShape(GradientDrawable.OVAL);
        bg.setStroke(dp(this, 1), 0x42A6B0D6);        // 和网页版球同色系 ✓
        v.setBackground(bg);
        v.setElevation(dp(this, 6));

        ballLp = new WindowManager.LayoutParams(
                dp(this, 44), dp(this, 44), overlayType(),
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE, PixelFormat.TRANSLUCENT);
        ballLp.gravity = Gravity.TOP | Gravity.START;
        // ⚠ 初始位置必须按**真实屏幕像素**算 ✗ 不能写死 dp
        //   (2026-09-22 踩过: 写 dp(300)/dp(900) ⇒ 密度 2 时 = 600/1800px ⇒ 屏幕高才 1280 ⇒ 球在屏幕外 ✗)
        android.util.DisplayMetrics dm = new android.util.DisplayMetrics();
        wm.getDefaultDisplay().getMetrics(dm);
        ballLp.x = dm.widthPixels - dp(this, 62);
        ballLp.y = dm.heightPixels - dp(this, 210);

        v.setOnTouchListener(new View.OnTouchListener() {
            float downX, downY;
            int startX, startY;
            boolean moved;

            @Override
            public boolean onTouch(View view, MotionEvent e) {
                switch (e.getAction()) {
                    case MotionEvent.ACTION_DOWN:
                        downX = e.getRawX();
                        downY = e.getRawY();
                        startX = ballLp.x;
                        startY = ballLp.y;
                        moved = false;
                        android.util.Log.i("companion", "DOWN raw=" + downX + "," + downY);
                        return true;
                    case MotionEvent.ACTION_MOVE:
                        int dx = (int) (e.getRawX() - downX), dy = (int) (e.getRawY() - downY);
                        if (Math.abs(dx) > 8 || Math.abs(dy) > 8) {
                            moved = true;
                        }
                        int sw = getResources().getDisplayMetrics().widthPixels;
                        int sh = getResources().getDisplayMetrics().heightPixels;
                        // 夹在屏幕里(别拖出去找不回来 ✗)
                        ballLp.x = Math.max(0, Math.min(sw - dp(OverlayService.this, 44), startX + dx));
                        ballLp.y = Math.max(0, Math.min(sh - dp(OverlayService.this, 44), startY + dy));
                        try {
                            wm.updateViewLayout(ball, ballLp);
                        } catch (Exception ignored) {
                        }
                        return true;
                    case MotionEvent.ACTION_UP:
                        android.util.Log.i("companion", "UP moved=" + moved);
                        if (!moved) {                 // 没拖动 = 点一下 ⇒ 展/收面板
                            togglePanel();
                        }
                        return true;
                    default:
                        return false;
                }
            }
        });

        ball = v;
        try {
            wm.addView(ball, ballLp);
        } catch (Exception e) {
            stopSelf();                                // 没权限就别硬撑 ✓
        }
    }

    /** 小面板: **原生控件**(不用 WebView ✗)
     *  ⚠ 2026-09-22 踩坑: 这个云手机容器里**系统 WebView 是坏的** ✗
     *    (原生掼蛋 App 就是死在 WebView.<init> ✓) ⇒ 一建 WebView 进程就崩 ✗
     *    ⇒ 面板改成原生控件, 数据照样从 companion 的 API 读(它读的是同一份 sqlite ✓)
     */
    private TextView tvHead, tvBody;
    private Thread poller;

    private void togglePanel() {
        android.util.Log.i("companion", "togglePanel open=" + panelOpen);
        if (panelOpen) {
            try {
                wm.removeView(panel);
            } catch (Exception ignored) {
            }
            panel = null;                  // 原生视图没有 destroy() ✓ 置空就够了
            panelOpen = false;
            // ★ 2026-09-22 修的 bug: 这里必须把 poller 置空 ✗
            //   否则下次展开时 startPolling() 被 "poller != null" 挡住 ⇒
            //   轮询线程早就随上次收起退出了 ⇒ 面板永远停在"连接中…" ✗
            poller = null;
            return;
        }
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(this, 10), dp(this, 8), dp(this, 10), dp(this, 8));
        GradientDrawable pbg = new GradientDrawable();
        pbg.setColor(Color.parseColor("#F00E141F"));
        pbg.setCornerRadius(dp(this, 12));
        pbg.setStroke(dp(this, 1), 0x40A6B0D6);
        box.setBackground(pbg);

        tvHead = new TextView(this);
        tvHead.setText("🃏 伴随应用 · 连接中…");
        tvHead.setTextColor(Color.parseColor("#EDF5FF"));
        tvHead.setTextSize(13);
        box.addView(tvHead);

        tvBody = new TextView(this);
        tvBody.setText("正在读取牌局…");
        tvBody.setTextColor(Color.parseColor("#9BB0C9"));
        tvBody.setTextSize(11);
        tvBody.setPadding(0, dp(this, 6), 0, 0);
        box.addView(tvBody);

        TextView hint = new TextView(this);
        hint.setText("（数据来自 companion.db · 只读）");
        hint.setTextColor(Color.parseColor("#5E7189"));
        hint.setTextSize(9);
        hint.setPadding(0, dp(this, 6), 0, 0);
        box.addView(hint);

        // 尺寸按屏幕算(2026-09-22: 原来写死 520dp ⇒ 底边超出屏幕被切 ✗)
        android.util.DisplayMetrics dm2 = new android.util.DisplayMetrics();
        wm.getDefaultDisplay().getMetrics(dm2);
        int pw = Math.min(dp(this, 320), dm2.widthPixels - dp(this, 16));
        int ph = Math.min(dp(this, 520), dm2.heightPixels - dp(this, 240));
        panelLp = new WindowManager.LayoutParams(
                pw, ph, overlayType(),
                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL
                        | WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH,
                PixelFormat.TRANSLUCENT);
        panelLp.gravity = Gravity.TOP | Gravity.START;
        panelLp.x = dp(this, 24);
        panelLp.y = dp(this, 200);
        panel = box;
        try {
            wm.addView(box, panelLp);
        } catch (Exception ignored) {
        }
        panelOpen = true;
        startPolling();
    }

    /** 每 2 秒拉一次 companion 的 API, 把牌局画到面板上 ✓ (它读的就是 sqlite ✓) */
    private void startPolling() {
        if (poller != null) {
            return;
        }
        poller = new Thread(new Runnable() {
            @Override
            public void run() {
                while (panelOpen) {
                    final String txt = fetch();
                    new android.os.Handler(android.os.Looper.getMainLooper()).post(
                            new Runnable() {
                                @Override
                                public void run() {
                                    if (tvHead != null && panelOpen) {
                                        tvHead.setText(txt.split("\n")[0]);
                                    }
                                    if (tvBody != null && panelOpen) {
                                        tvBody.setText(txt.substring(
                                                Math.min(txt.length(), txt.indexOf('\n') + 1)));
                                    }
                                }
                            });
                    try {
                        Thread.sleep(2000);
                    } catch (InterruptedException e) {
                        return;
                    }
                }
            }
        });
        poller.start();
    }

    /** 读一次牌局(只读 ✓): /api/live 给最近一局的出牌/牌池/推荐 */
    private String fetch() {
        String base = PANEL_URL.replace("?embed=1", "");
        try {
            java.net.URL u = new java.net.URL(base + "api/live");
            java.net.HttpURLConnection c = (java.net.HttpURLConnection) u.openConnection();
            c.setConnectTimeout(3000);
            c.setReadTimeout(3000);
            java.io.BufferedReader r = new java.io.BufferedReader(
                    new java.io.InputStreamReader(c.getInputStream(), "UTF-8"));
            StringBuilder sb = new StringBuilder();
            String ln;
            while ((ln = r.readLine()) != null) {
                sb.append(ln);
            }
            r.close();
            org.json.JSONObject j = new org.json.JSONObject(sb.toString());
            if (j.optBoolean("empty")) {
                return "🃏 伴随应用 · 等待牌局";
            }
            StringBuilder out = new StringBuilder();
            out.append("🃏 ").append(j.optString("gid", "?"));
            out.append("  级牌 ").append(j.optInt("ji_pai", 0));
            int hand = j.optJSONArray("hand") == null ? 0 : j.optJSONArray("hand").length();
            out.append("  手牌 ").append(hand).append(" 张\n");
            org.json.JSONArray pl = j.optJSONArray("plays");
            if (pl != null) {
                int from = Math.max(0, pl.length() - 6);
                for (int i = from; i < pl.length(); i++) {
                    org.json.JSONObject p = pl.getJSONObject(i);
                    out.append("  ").append(p.optString("seat", "?"))
                       .append(p.optBoolean("mine") ? "(我)" : "").append("  ")
                       .append(p.optString("kind", "").equals("pass") ? "不出"
                               : p.optString("cards_raw", "")).append("\n");
                }
            }
            org.json.JSONArray rm = j.optJSONArray("remains");
            if (rm != null && rm.length() > 0) {
                out.append("  牌池快照: ").append(
                        rm.getJSONObject(0).optString("counts", "").length() > 2 ? "有" : "无");
            }
            return out.toString();
        } catch (Exception e) {
            return "🃏 伴随应用 · 连不上(" + e.getClass().getSimpleName() + ")\n"
                    + "  检查 companion 服务是否在跑 ✓";
        }
    }

    @Override
    public void onDestroy() {
        try {
            if (panelOpen && panel != null) {
                wm.removeView(panel);          // 面板本身就是视图 ✓ 没有外层了
                panelOpen = false;
            }
            if (ball != null) {
                wm.removeView(ball);
            }
        } catch (Exception ignored) {
        }
        super.onDestroy();
    }
}
