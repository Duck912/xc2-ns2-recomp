// SPDX-License-Identifier: GPL-3.0-or-later
// Play mode settings menu: two-pane card-row UI (left option cards, right live description & status),
// bilingual Simplified Chinese / English, with XC2 Aegis Deep Ocean + Emerald / Gold styling.
//
// Two-pane card-row interaction & layout adapted from totk-pc-recomp (runtime/ui/option_rows.cpp & menu.cpp,
// MIT License, https://github.com/valentderah/totk-pc-recomp) and SavageWindRecomp (MIT License).
#include "play_ui.h"

#include <algorithm>
#include <cfloat>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "imgui.h"
#include "imgui_internal.h"
#include "nxrt/audio_sink.h"
#include "nxrt/extras.h"
#include "extras/temporal.h"
#include "nxrt/frame_limiter.h"
#include "nxrt/input_source.h"
#include "nxrt/lowlat.h"
#include "nxrt/overlay.h"
#include "nxrt/platform.h"
#include "play_game.h"

namespace nxrt::play {

namespace {

namespace hid = nxrt::hid;

// ---- XC2 Aegis palette --------------------------------------------------------------------------------------------------------------
const ImVec4 kGold(0.94f, 0.78f, 0.36f, 1.0f);
const ImVec4 kEmerald(0.28f, 0.86f, 0.76f, 1.0f);
const ImVec4 kOrange(0.95f, 0.64f, 0.28f, 1.0f);
const ImVec4 kDimText(0.60f, 0.68f, 0.76f, 1.0f);
const ImVec4 kPressed(0.18f, 0.56f, 0.46f, 1.0f);
const ImVec4 kReleased(0.14f, 0.20f, 0.28f, 1.0f);

const ImU32 kColGold = IM_COL32(240, 198, 92, 255);
const ImU32 kColGoldLine = IM_COL32(240, 198, 92, 115);
const ImU32 kColEmerald = IM_COL32(72, 220, 194, 255);
const ImU32 kColOrange = IM_COL32(242, 168, 78, 255);
const ImU32 kColWhite = IM_COL32(242, 246, 250, 255);
const ImU32 kColDim = IM_COL32(150, 170, 190, 255);
const ImU32 kColGrey = IM_COL32(105, 120, 136, 255);

// ---- Language state -----------------------------------------------------------------------------------------------------------------
bool g_zh = true;
const char* tr(const char* zh, const char* en) { return g_zh ? zh : en; }

// ---- Static option tables -----------------------------------------------------------------------------------------------------------
constexpr int kWindowModeCount = 3;
constexpr const char* kWindowModeKeys[kWindowModeCount] = {"windowed", "borderless", "exclusive"};
constexpr const char* kWindowModeZh[kWindowModeCount] = {"窗口模式", "无边框全屏", "独占全屏"};
constexpr const char* kWindowModeEn[kWindowModeCount] = {"Windowed", "Borderless", "Exclusive"};

constexpr int kSizePresets[][2] = {{1280, 720}, {1600, 900}, {1920, 1080}, {2560, 1440}, {3840, 2160}};
constexpr const char* kSizeLabels[] = {"1280 x 720", "1600 x 900", "1920 x 1080", "2560 x 1440", "3840 x 2160"};
constexpr int kSizePresetCount = static_cast<int>(sizeof kSizePresets / sizeof kSizePresets[0]);

constexpr int kFpsChoices[] = {-1, 0, 30, 60, 72, 90, 120, 144, 165, 240, 360};
constexpr int kFpsChoiceCount = static_cast<int>(sizeof kFpsChoices / sizeof kFpsChoices[0]);

constexpr const char* kAnisoZh[] = {"游戏默认", "2x", "4x", "8x", "16x"};
constexpr const char* kAnisoEn[] = {"Game default", "2x", "4x", "8x", "16x"};
constexpr int kAnisoValues[] = {0, 2, 4, 8, 16};
constexpr int kAnisoCount = static_cast<int>(sizeof kAnisoValues / sizeof kAnisoValues[0]);

constexpr const char* kAstcValues[] = {"fast", "high", "uncompressed"};
constexpr const char* kAstcZh[] = {"快速 (BC7)", "高质量 (后台重编码)", "无压缩 (RGBA8)"};
constexpr const char* kAstcEn[] = {"Fast (BC7)", "High (background)", "Uncompressed (RGBA8)"};
constexpr int kAstcCount = static_cast<int>(sizeof kAstcValues / sizeof kAstcValues[0]);

constexpr const char* kPromptZh[kPromptStyleCount] = {"Switch 原版", "Xbox", "PlayStation", "键盘与鼠标", "自动跟随设备"};
constexpr const char* kPromptEn[kPromptStyleCount] = {"Switch", "Xbox", "PlayStation", "Keyboard & Mouse", "Auto"};

constexpr const char* kCornerZh[] = {"左上角", "右上角", "左下角", "右下角"};
constexpr const char* kCornerEn[] = {"Top left", "Top right", "Bottom left", "Bottom right"};
constexpr int kCornerCount = 4;

constexpr const char* kFpsDetailZh[] = {"仅显示帧率", "帧率 + 帧时间", "完整 (含 1% Low / 最慢帧)"};
constexpr const char* kFpsDetailEn[] = {"FPS only", "FPS & frame time", "Full (1% low & worst)"};
constexpr int kFpsDetailCount = 3;

constexpr const char* kHdrModeZh[] = {"关闭 (SDR)", "自动", "强制开启", "Switch 2 原生 HDR"};
constexpr const char* kHdrModeEn[] = {"Off (SDR)", "Auto", "On", "Native HDR"};

constexpr const char* kHdrFmtZh[] = {"自动", "HDR10", "scRGB"};
constexpr const char* kHdrFmtEn[] = {"Auto", "HDR10", "scRGB"};

constexpr const char* kLatencyZh[] = {"关闭", "自动", "开启", "增强 (Boost)"};
constexpr const char* kLatencyEn[] = {"Off", "Auto", "On", "Boost"};

constexpr const char* kUpscaleZh[] = {"关闭", "FSR 1 (空间锐化)", "FSR 3", "DLSS", "XeSS", "NIS (空间锐化)", "DLAA"};
constexpr const char* kUpscaleEn[] = {"Off", "FSR 1 (spatial)", "FSR 3", "DLSS", "XeSS", "NIS (spatial)", "DLAA"};
constexpr extras::UpscaleMode kUpscaleOrder[] = {
    extras::UpscaleMode::Off,  extras::UpscaleMode::Fsr1, extras::UpscaleMode::Nis,
    extras::UpscaleMode::Fsr3, extras::UpscaleMode::Dlss, extras::UpscaleMode::Dlaa,
};
constexpr int kUpscaleOrderCount = static_cast<int>(sizeof kUpscaleOrder / sizeof kUpscaleOrder[0]);

constexpr const char* kUpscaleQualZh[] = {"原生抗锯齿 (100%)", "质量 (67%)", "平衡 (59%)", "性能 (50%)", "超高性能 (33%)", "自定义场景缩放"};
constexpr const char* kUpscaleQualEn[] = {"Native AA (100%)", "Quality (67%)", "Balanced (59%)", "Performance (50%)", "Ultra Perf (33%)", "Custom"};

constexpr Trig kTrigChoices[] = {Trig::Press, Trig::Tap, Trig::Hold, Trig::Toggle, Trig::DoubleTap};

struct SwitchButton {
    const char* name;
    hid::NpadButtonBit bit;
};
constexpr SwitchButton kSwitchButtons[] = {
    {"A", hid::kBtnA},         {"B", hid::kBtnB},         {"X", hid::kBtnX},         {"Y", hid::kBtnY},
    {"L", hid::kBtnL},         {"R", hid::kBtnR},         {"ZL", hid::kBtnZL},       {"ZR", hid::kBtnZR},
    {"PLUS", hid::kBtnPlus},   {"MINUS", hid::kBtnMinus}, {"UP", hid::kBtnUp},       {"DOWN", hid::kBtnDown},
    {"LEFT", hid::kBtnLeft},   {"RIGHT", hid::kBtnRight}, {"LSTICK", hid::kBtnStickL}, {"RSTICK", hid::kBtnStickR},
};
constexpr int kSwitchButtonCount = static_cast<int>(sizeof kSwitchButtons / sizeof kSwitchButtons[0]);

constexpr const char* kPadSrcLabels[kPadSrcCount] = {
    "A / Cross (下)", "B / Circle (右)", "X / Square (左)", "Y / Triangle (上)",
    "LB / L1",        "RB / R1",         "LT / L2",         "RT / R2",
    "Menu / Options", "View / Create",   "左摇杆按下 (L3)", "右摇杆按下 (R3)",
    "十字键 上",       "十字键 下",        "十字键 左",        "十字键 右",
};
constexpr const char* kPadChoiceNames[] = {
    "默认", "无",
    "A", "B", "X", "Y", "L", "R", "ZL", "ZR", "Plus", "Minus",
    "方向 上", "方向 下", "方向 左", "方向 右", "L3", "R3",
};
constexpr int kPadChoiceCount = static_cast<int>(sizeof kPadChoiceNames / sizeof kPadChoiceNames[0]);

// ---- Working state ------------------------------------------------------------------------------------------------------------------
struct Page {
    bool loaded = false;
    bool dirty = false;
    Settings edit;
    Ctx ctx = Ctx::Play;
    int rebind = -1;
    bool link_pitch = true;
    bool out_tab_open = false;
    char out_text[kActCount][128] = {};
    std::string out_err[kActCount];
    bool fps_capture = false;
    std::string notice;
    bool notice_warn = false;
    std::vector<std::string> monitors;
    double monitors_at = -1e9;
    std::vector<std::string> audio_devices;
    bool audio_loaded = false;
    int active_tab = 0;   // 0 Display, 1 Graphics, 2 Audio, 3 Controls, 4 Overlay
};

void mark(Page& p) { p.dirty = true; }
const char* cstr(const char* s) { return s ? s : ""; }
const char* act_label(Act a) { return a == Act::None ? tr("无 (禁用)", "none") : act_info(a).name; }
float px(float v) { return v * ImGui::GetFontSize() / 18.0f; }

bool upscale_available(extras::UpscaleMode m) {
    switch (m) {
        case extras::UpscaleMode::Off:
        case extras::UpscaleMode::Fsr1:
        case extras::UpscaleMode::Nis: return true;
        case extras::UpscaleMode::Fsr3: return extras::temporal_ffx_available();
        case extras::UpscaleMode::Dlss:
        case extras::UpscaleMode::Dlaa: return extras::temporal_dlss_available();
        default: return false;
    }
}

void stop_rebind(UiHost& host, Page& p) {
    if (p.rebind >= 0 && host.capturing()) host.cancel_capture();
    p.rebind = -1;
}

void stop_fps_capture(UiHost& host, Page& p) {
    if (p.fps_capture && host.capturing()) host.cancel_capture();
    p.fps_capture = false;
}

std::vector<int> conflicts_of(const Page& p, int row) {
    std::vector<int> out;
    const Binding& a = p.edit.bindings[static_cast<std::size_t>(row)];
    if (a.in.kind == InKind::None) return out;
    for (std::size_t i = 0; i < p.edit.bindings.size(); ++i) {
        const Binding& b = p.edit.bindings[i];
        if (static_cast<int>(i) != row && b.ctx == a.ctx && b.in == a.in && b.trig == a.trig) out.push_back(static_cast<int>(i));
    }
    return out;
}

void set_notice(Page& p, const std::string& text, bool warn) {
    p.notice = text;
    p.notice_warn = warn;
}

void refresh_out_text(Page& p) {
    for (int a = 1; a < kActCount; ++a) {
        const std::string text = output_text(p.edit.out[a]);
        std::snprintf(p.out_text[a], sizeof p.out_text[a], "%s", text.c_str());
        p.out_err[a].clear();
    }
}

void sanitize(Settings& s) {
    std::vector<Binding>& v = s.bindings;
    v.erase(std::remove_if(v.begin(), v.end(), [](const Binding& b) { return b.in.kind == InKind::None; }), v.end());
    for (Binding& b : v) b.ms = std::clamp(b.ms, 0, 5000);
    s.display.width = std::clamp(s.display.width, 320, 16384);
    s.display.height = std::clamp(s.display.height, 320, 16384);
    s.display.render_width = s.display.render_width <= 0 ? 0 : std::clamp(s.display.render_width, 320, 16384);
    s.display.render_height = s.display.render_height <= 0 ? 0 : std::clamp(s.display.render_height, 320, 16384);
    extras::HdrSettings& h = s.extras.hdr;
    h.peak_nits = h.peak_nits <= 0 ? 0 : std::clamp(h.peak_nits, 200.0, 10000.0);
    h.paper_white_nits = h.paper_white_nits <= 0 ? 0 : std::clamp(h.paper_white_nits, 80.0, 500.0);
    h.highlight_boost = std::clamp(h.highlight_boost, 0.0, 2.0);
    s.extras.upscale.sharpness = std::clamp(s.extras.upscale.sharpness, 0.0, 1.0);
    s.extras.picture = extras::picture_clamped(s.extras.picture);
    s.audio.volume = std::clamp(s.audio.volume, 0.0, 1.0);
    s.display.monitor = std::clamp(s.display.monitor, 0, 32);
    if (s.audio.device.empty()) s.audio.device = "default";
}

void apply_now(UiHost& host, Page& p) {
    stop_rebind(host, p);
    p.edit.fps = host.settings().fps;
    sanitize(p.edit);
    host.apply(p.edit);
    p.dirty = false;
    set_notice(p, tr("设置已应用并保存", "Settings applied and saved"), false);
}

void revert_to_saved(UiHost& host, Page& p) {
    stop_rebind(host, p);
    p.edit = host.settings();
    p.edit.fps = host.settings().fps;
    extras::set_picture_live(p.edit.extras.picture);
    refresh_out_text(p);
    p.dirty = false;
    set_notice(p, tr("已放弃未保存的修改", "Changes discarded"), false);
}

void load_factory(UiHost& host, Page& p) {
    stop_rebind(host, p);
    p.edit = host.factory();
    p.edit.fps = host.settings().fps;
    extras::set_picture_live(p.edit.extras.picture);
    refresh_out_text(p);
    mark(p);
    set_notice(p, tr("已载入默认配置，点击「应用并保存」生效", "Factory defaults loaded; click Apply & Save"), false);
}

void set_fps_live(UiHost& host, const FpsSettings& f) {
    Settings cur = host.settings();
    cur.fps = f;
    host.apply(cur);
}

void poll_capture(UiHost& host, Page& p) {
    InputId id;
    if (host.capture_result(&id)) {
        const std::string name = input_name(id);
        const bool reserved = host.reserved_key(id);
        if (p.fps_capture) {
            if (reserved) {
                set_notice(p, name + tr(" 是菜单快捷键，无法绑定为帧率键（按 Esc 取消）", " opens the menu; press another key or Esc"), true);
                host.begin_capture();
                return;
            }
            p.fps_capture = false;
            if (id.kind == InKind::Key) {
                Settings cur = host.settings();
                cur.fps.key = id;
                host.apply(cur);
                set_notice(p, std::string(tr("帧率快捷键已改为 ", "FPS hotkey set to ")) + name, false);
            }
        } else if (p.rebind >= 0 && p.rebind < static_cast<int>(p.edit.bindings.size())) {
            const Settings cur = host.settings();
            if (reserved || (id.kind == InKind::Key && id == cur.fps.key)) {
                set_notice(p, name + tr(" 为系统保留键，请按其他键（Esc 取消）", " is reserved; press another key or Esc"), true);
                host.begin_capture();
                return;
            }
            p.edit.bindings[static_cast<std::size_t>(p.rebind)].in = id;
            mark(p);
            const std::vector<int> other = conflicts_of(p, p.rebind);
            if (other.empty()) {
                set_notice(p, std::string(tr("已绑定 ", "Bound ")) + name, false);
            } else {
                const Binding& o = p.edit.bindings[static_cast<std::size_t>(other[0])];
                set_notice(p, name + tr(" 与以下操作冲突：", " conflicts with: ") + act_label(o.act), true);
            }
        }
        p.rebind = -1;
    } else if ((p.rebind >= 0 || p.fps_capture) && !host.capturing()) {
        p.rebind = -1;
        p.fps_capture = false;
        set_notice(p, tr("已取消按键捕获", "Capture cancelled"), false);
    }
}

void refresh_monitors(Page& p) {
    const double now = ImGui::GetTime();
    if (p.monitors_at >= 0.0 && now - p.monitors_at < 2.0) return;
    p.monitors_at = now;
    p.monitors.clear();
    const int n = platform::display_count();
    for (int i = 1; i <= n; ++i) {
        char buf[192];
        if (platform::display_name(i, buf, sizeof buf)) p.monitors.emplace_back(buf);
    }
}

void load_audio_devices(Page& p) {
    p.audio_devices.clear();
    for (const audio::OutputDevice& d : audio::list_output_devices())
        if (!d.name.empty()) p.audio_devices.push_back(d.name);
    p.audio_loaded = true;
}

int window_mode_index(const std::string& mode) {
    for (int i = 0; i < kWindowModeCount; ++i)
        if (mode == kWindowModeKeys[i]) return i;
    return 0;
}

uint64_t pad_choice_value(int c) {
    if (c == 0) return kPadDefault;
    if (c == 1) return 0;
    return static_cast<uint64_t>(hid::btn(kSwitchButtons[c - 2].bit));
}

int pad_choice_of(uint64_t v) {
    for (int c = 0; c < kPadChoiceCount; ++c)
        if (pad_choice_value(c) == v) return c;
    return -1;
}

void fps_label_text(int fps, char* buf, std::size_t n) {
    if (fps < 0) std::snprintf(buf, n, "%s", tr("跟随显示器刷新率", "Refresh rate"));
    else if (fps == 0) std::snprintf(buf, n, "%s", tr("无限制", "Unlimited"));
    else std::snprintf(buf, n, "%d fps", fps);
}

// ---- Two-pane card-row engine (adapted from totk-pc-recomp option_rows.cpp, MIT) ----------------------------------------------------
struct DescInfo {
    std::string title;
    std::string body;
    bool restart = false;
    bool live = false;
    bool valid = false;
};

struct PaneState {
    DescInfo hover;
    DescInfo focus;
    DescInfo first;
    DescInfo shown;
    float bottom_reserve = 0.0f;
    bool held = false;
};

PaneState g_pane;

void record_desc(const char* title, const char* body, bool restart, bool live, bool hov, bool foc) {
    DescInfo d;
    d.title = title ? title : "";
    d.body = body ? body : "";
    d.restart = restart;
    d.live = live;
    d.valid = true;
    if (hov) g_pane.hover = d;
    if (foc) g_pane.focus = d;
    if (!g_pane.first.valid) g_pane.first = d;
}

void pane_begin(const char* id, float bottom_reserve) {
    g_pane.bottom_reserve = bottom_reserve;
    g_pane.hover.valid = false;
    g_pane.focus.valid = false;
    g_pane.first.valid = false;
    ImVec2 avail = ImGui::GetContentRegionAvail();
    avail.y = std::max(px(120.0f), avail.y - bottom_reserve);
    ImGui::PushID(id);
    ImGui::BeginChild("##rows_pane", ImVec2(avail.x * 0.59f, avail.y), ImGuiChildFlags_NavFlattened);
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(ImGui::GetStyle().ItemSpacing.x, px(7.0f)));
}

void pane_end(const LiveStatus& live) {
    ImGui::PopStyleVar();
    ImGui::EndChild();

    if (g_pane.hover.valid) g_pane.shown = g_pane.hover;
    else if (g_pane.focus.valid) g_pane.shown = g_pane.focus;
    else if (!g_pane.shown.valid && g_pane.first.valid) g_pane.shown = g_pane.first;

    ImGui::SameLine(0.0f, 0.0f);
    const ImVec2 p = ImGui::GetCursorScreenPos();
    ImVec2 avail = ImGui::GetContentRegionAvail();
    avail.y = std::max(px(120.0f), avail.y - g_pane.bottom_reserve);
    const float gap = px(22.0f);
    ImGui::GetWindowDrawList()->AddLine(ImVec2(p.x + gap * 0.5f, p.y + px(4.0f)),
                                        ImVec2(p.x + gap * 0.5f, p.y + avail.y - px(4.0f)), kColGoldLine, 1.0f);

    ImGui::SetCursorScreenPos(ImVec2(p.x + gap, p.y));
    ImGui::BeginChild("##desc_pane", ImVec2(0.0f, avail.y), 0, ImGuiWindowFlags_NoNav);

    // Top: Option explanation card
    const float status_h = px(155.0f);
    const float desc_h = std::max(px(100.0f), avail.y - status_h - px(12.0f));
    {
        const ImVec2 cp = ImGui::GetCursorScreenPos();
        const float cw = ImGui::GetContentRegionAvail().x;
        ImDrawList* dl = ImGui::GetWindowDrawList();
        dl->AddRectFilled(cp, ImVec2(cp.x + cw, cp.y + desc_h), IM_COL32(8, 16, 28, 150), px(10.0f));
        dl->AddRect(cp, ImVec2(cp.x + cw, cp.y + desc_h), IM_COL32(60, 125, 145, 95), px(10.0f), 0, 1.0f);
        ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(px(14.0f), px(12.0f)));
        ImGui::BeginChild("##desc_inner", ImVec2(cw, desc_h), ImGuiChildFlags_AlwaysUseWindowPadding, ImGuiWindowFlags_NoNav);
        ImGui::PopStyleVar();
        if (g_pane.shown.valid) {
            ImGui::PushStyleColor(ImGuiCol_Text, kGold);
            ImGui::TextWrapped("%s", g_pane.shown.title.c_str());
            ImGui::PopStyleColor();
            if (g_pane.shown.restart) {
                ImGui::PushStyleColor(ImGuiCol_Text, kOrange);
                ImGui::TextUnformatted(tr("● 需重启游戏后生效", "● Applies after restart"));
                ImGui::PopStyleColor();
            } else if (g_pane.shown.live) {
                ImGui::PushStyleColor(ImGuiCol_Text, kEmerald);
                ImGui::TextUnformatted(tr("● 修改后实时生效", "● Applies live"));
                ImGui::PopStyleColor();
            }
            ImGui::Spacing();
            ImGui::Separator();
            ImGui::Spacing();
            ImGui::PushTextWrapPos(0.0f);
            ImGui::TextUnformatted(g_pane.shown.body.c_str());
            ImGui::PopTextWrapPos();
        }
        ImGui::EndChild();
    }

    ImGui::Dummy(ImVec2(0.0f, px(6.0f)));

    // Bottom: Live status card
    {
        const ImVec2 cp = ImGui::GetCursorScreenPos();
        const float cw = ImGui::GetContentRegionAvail().x;
        const float ch = std::max(px(110.0f), ImGui::GetContentRegionAvail().y);
        ImDrawList* dl = ImGui::GetWindowDrawList();
        dl->AddRectFilled(cp, ImVec2(cp.x + cw, cp.y + ch), IM_COL32(8, 16, 28, 165), px(10.0f));
        dl->AddRect(cp, ImVec2(cp.x + cw, cp.y + ch), IM_COL32(72, 220, 194, 80), px(10.0f), 0, 1.0f);
        ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(px(14.0f), px(10.0f)));
        ImGui::BeginChild("##status_inner", ImVec2(cw, ch), ImGuiChildFlags_AlwaysUseWindowPadding, ImGuiWindowFlags_NoNav);
        ImGui::PopStyleVar();

        ImGui::PushStyleColor(ImGuiCol_Text, kEmerald);
        ImGui::TextUnformatted(tr("实时运行状态", "Live Status"));
        ImGui::PopStyleColor();
        ImGui::Separator();
        ImGui::Text("%s: %d x %d  (%.1f fps)", tr("画面", "Output"), live.width, live.height, live.fps);
        ImGui::Text("%s: %.1f Hz  |  %s", tr("显示器", "Display"), live.refresh_hz, cstr(live.present_mode));
        const extras::HdrState hs = extras::hdr_state();
        ImGui::Text("HDR: %s  (%s)", hs.scene_hdr ? tr("开", "On") : tr("关", "Off"), extras::output_kind_name(hs.output));
        const int backlog = gfx::shader_backlog();
        if (backlog > 0) ImGui::TextColored(kOrange, "%s: %d", tr("后台着色器编译剩余", "Shaders left"), backlog);
        else ImGui::TextColored(kDimText, "%s", tr("着色器缓存已就绪", "Shader cache ready"));
        if (live.pads > 0) ImGui::TextColored(kDimText, "%s: %s", tr("手柄", "Pad"), live.pad_name.c_str());
        else ImGui::TextColored(kDimText, "%s", tr("手柄: 未连接 (键鼠模式)", "Pad: None (KB/Mouse)"));

        ImGui::EndChild();
    }

    ImGui::EndChild();
    ImGui::PopID();
}

void card_group(const char* zh, const char* en) {
    ImGui::Spacing();
    const char* title = tr(zh, en);
    ImGui::PushStyleColor(ImGuiCol_Text, kGold);
    ImGui::TextUnformatted(title);
    ImGui::PopStyleColor();
    const ImVec2 p = ImGui::GetCursorScreenPos();
    const float w = ImGui::GetContentRegionAvail().x;
    ImGui::GetWindowDrawList()->AddLine(ImVec2(p.x, p.y - px(2.0f)), ImVec2(p.x + w, p.y - px(2.0f)),
                                        IM_COL32(240, 198, 92, 90), 1.0f);
    ImGui::Dummy(ImVec2(0.0f, px(2.0f)));
}

// Core interactive option card. Returns: -1 step down, +1 step up, 2 clicked/A, 0 none.
int draw_card_raw(const char* id, const char* label, const char* value, const char* desc,
                  bool arrows, bool restart, bool live, bool accent_val, bool disabled, float progress = -1.0f) {
    const float fs = ImGui::GetFontSize();
    const float w = ImGui::GetContentRegionAvail().x;
    const float h = (restart || live) ? fs * 2.45f : fs * 2.15f;
    const ImVec2 p = ImGui::GetCursorScreenPos();

    ImGui::PushID(id);
    const bool clicked = ImGui::InvisibleButton("##card", ImVec2(w, h));
    const bool hov = ImGui::IsItemHovered();
    const bool foc = ImGui::IsItemFocused();
    ImGui::PopID();

    int step = (clicked && !disabled) ? 2 : 0;
    g_pane.held = false;
    if (foc && !disabled) {
        if (ImGui::IsKeyPressed(ImGuiKey_LeftArrow) || ImGui::IsKeyPressed(ImGuiKey_GamepadDpadLeft)) step = -1;
        if (ImGui::IsKeyPressed(ImGuiKey_RightArrow) || ImGui::IsKeyPressed(ImGuiKey_GamepadDpadRight)) step = 1;
        static const ImGuiKey kStepKeys[] = {ImGuiKey_LeftArrow, ImGuiKey_RightArrow, ImGuiKey_GamepadDpadLeft, ImGuiKey_GamepadDpadRight};
        for (ImGuiKey k : kStepKeys) {
            if (ImGui::GetKeyData(k)->DownDuration > 0.7f) g_pane.held = true;
            ImGui::SetKeyOwner(k, ImGui::GetItemID());
        }
    }

    record_desc(label, desc, restart, live, hov, foc);

    ImDrawList* dl = ImGui::GetWindowDrawList();
    ImFont* font = ImGui::GetFont();
    const float r = px(9.0f);
    const float pad = px(15.0f);
    const bool hi = hov || foc;

    const ImU32 bg = disabled ? IM_COL32(10, 16, 26, 95)
                              : hi ? IM_COL32(28, 78, 92, 130) : IM_COL32(10, 20, 34, 155);
    const ImU32 brd = disabled ? IM_COL32(80, 95, 110, 45)
                               : hi ? kColGold : IM_COL32(72, 145, 168, 70);
    dl->AddRectFilled(p, ImVec2(p.x + w, p.y + h), bg, r);
    dl->AddRect(p, ImVec2(p.x + w, p.y + h), brd, r, 0, hi ? 1.8f : 1.0f);

    // Optional progress bar along bottom inside card (for sliders)
    if (progress >= 0.0f) {
        const float t = std::clamp(progress, 0.0f, 1.0f);
        const float by = p.y + h - px(4.5f);
        const float bx0 = p.x + pad;
        const float bx1 = p.x + w - pad;
        dl->AddRectFilled(ImVec2(bx0, by), ImVec2(bx1, by + px(2.5f)), IM_COL32(255, 255, 255, 28), px(2.0f));
        if (t > 0.001f)
            dl->AddRectFilled(ImVec2(bx0, by), ImVec2(bx0 + (bx1 - bx0) * t, by + px(2.5f)),
                              hi ? kColGold : kColEmerald, px(2.0f));
    }

    const float ty = p.y + ((restart || live) ? fs * 0.28f : (h - fs) * 0.5f);
    const float ny = p.y + fs * 1.42f;
    float right = p.x + w - pad;

    if (arrows && value && value[0]) {
        const float aw = fs * 0.36f;
        const float agap = fs * 0.45f;
        const float cy = ty + fs * 0.50f;
        const float val_w = ImGui::CalcTextSize(value).x;
        const float rx = right - aw;
        const float lx = rx - agap - val_w - agap - aw;
        const ImU32 ac = disabled ? kColGrey : hi ? kColGold : IM_COL32(150, 185, 200, 220);
        dl->AddTriangleFilled(ImVec2(lx, cy), ImVec2(lx + aw, cy - aw * 0.8f), ImVec2(lx + aw, cy + aw * 0.8f), ac);
        dl->AddTriangleFilled(ImVec2(rx + aw, cy), ImVec2(rx, cy - aw * 0.8f), ImVec2(rx, cy + aw * 0.8f), ac);
        if (clicked && !disabled) {
            const float mx = ImGui::GetIO().MousePos.x;
            if (mx >= lx - agap * 1.5f && mx <= lx + aw + agap) step = -1;
            else if (mx >= rx - agap && mx <= rx + aw + agap * 1.5f) step = 1;
        }
        right = rx - agap;
    }

    if (value && value[0]) {
        const float vw = ImGui::CalcTextSize(value).x;
        const ImU32 vc = disabled ? kColGrey : accent_val ? kColEmerald : kColWhite;
        dl->AddText(ImVec2(right - vw, ty), vc, value);
    }

    if (restart || live) {
        const float small = fs * 0.72f;
        const char* tag = restart ? tr("重启生效", "Restart") : tr("实时生效", "Live");
        const float tw = font->CalcTextSizeA(small, FLT_MAX, 0.0f, tag).x;
        dl->AddText(font, small, ImVec2(p.x + w - pad - tw, ny), restart ? kColOrange : kColDim, tag);
    }

    // Label on the left
    const ImU32 lc = disabled ? kColGrey : kColWhite;
    dl->AddText(ImVec2(p.x + pad, ty), lc, label);
    return step;
}

bool card_toggle(const char* id, const char* lzh, const char* len, const char* dzh, const char* den,
                 bool* val, bool restart = false, bool live = false) {
    const char* vtext = *val ? tr("开启", "On") : tr("关闭", "Off");
    const int s = draw_card_raw(id, tr(lzh, len), vtext, tr(dzh, den), true, restart, live, *val, false);
    if (s != 0) {
        *val = !(*val);
        return true;
    }
    return false;
}

bool card_choice(const char* id, const char* lzh, const char* len, const char* dzh, const char* den,
                 int* idx, const char* const* zh_names, const char* const* en_names, int count,
                 bool restart = false, bool live = false) {
    if (count <= 0) return false;
    *idx = std::clamp(*idx, 0, count - 1);
    const char* cur = g_zh ? zh_names[*idx] : en_names[*idx];
    const int s = draw_card_raw(id, tr(lzh, len), cur, tr(dzh, den), true, restart, live, false, false);
    if (s == -1) {
        *idx = (*idx + count - 1) % count;
        return true;
    }
    if (s == 1 || s == 2) {
        *idx = (*idx + 1) % count;
        return true;
    }
    return false;
}

bool card_choice_vec(const char* id, const char* lzh, const char* len, const char* dzh, const char* den,
                     int* idx, const std::vector<std::string>& items, bool restart = false) {
    const int count = static_cast<int>(items.size());
    if (count <= 0) return false;
    *idx = std::clamp(*idx, 0, count - 1);
    std::string disp = items[static_cast<std::size_t>(*idx)];
    if (disp.size() > 26) disp = disp.substr(0, 23) + "...";
    const int s = draw_card_raw(id, tr(lzh, len), disp.c_str(), tr(dzh, den), count > 1, restart, false, false, false);
    if (count > 1 && s == -1) {
        *idx = (*idx + count - 1) % count;
        return true;
    }
    if (count > 1 && (s == 1 || s == 2)) {
        *idx = (*idx + 1) % count;
        return true;
    }
    return false;
}

bool card_slider_f(const char* id, const char* lzh, const char* len, const char* dzh, const char* den,
                   double* val, double lo, double hi, double step, const char* fmt,
                   bool restart = false, bool live = false) {
    char buf[64];
    std::snprintf(buf, sizeof buf, fmt, *val);
    const float prog = (hi > lo) ? static_cast<float>((*val - lo) / (hi - lo)) : 0.0f;
    const int s = draw_card_raw(id, tr(lzh, len), buf, tr(dzh, den), true, restart, live, false, false, prog);
    if (s == -1 || s == 1 || s == 2) {
        const double mult = g_pane.held ? 5.0 : 1.0;
        const double delta = (s == -1 ? -1.0 : 1.0) * step * mult;
        double nv = *val + delta;
        if (s == 2 && nv > hi + 1e-6) nv = lo;
        nv = std::clamp(nv, lo, hi);
        if (std::fabs(nv - *val) > 1e-7) {
            *val = nv;
            return true;
        }
    }
    return false;
}

bool card_slider_i(const char* id, const char* lzh, const char* len, const char* dzh, const char* den,
                   int* val, int lo, int hi, int step, const char* fmt,
                   bool restart = false, bool live = false, const char* special_zero = nullptr, int min_nonzero = 0) {
    char buf[64];
    if (special_zero && *val <= 0) std::snprintf(buf, sizeof buf, "%s", special_zero);
    else std::snprintf(buf, sizeof buf, fmt, *val);
    const float prog = (hi > lo) ? static_cast<float>(std::max(0, *val - lo)) / static_cast<float>(hi - lo) : 0.0f;
    const int s = draw_card_raw(id, tr(lzh, len), buf, tr(dzh, den), true, restart, live, false, false, prog);
    if (s == -1 || s == 1 || s == 2) {
        const int mult = g_pane.held ? 5 : 1;
        int nv = *val + (s == -1 ? -1 : 1) * step * mult;
        if (special_zero && min_nonzero > 0) {
            if (*val <= 0 && (s == 1 || s == 2)) nv = min_nonzero;
            else if (*val > 0 && nv < min_nonzero) nv = 0;
        }
        if (s == 2 && nv > hi) nv = lo;
        nv = std::clamp(nv, lo, hi);
        if (nv != *val) {
            *val = nv;
            return true;
        }
    }
    return false;
}

bool card_button(const char* id, const char* lzh, const char* len, const char* dzh, const char* den,
                 const char* right_text = "", bool disabled = false) {
    const int s = draw_card_raw(id, tr(lzh, len), right_text, tr(dzh, den), false, false, true, true, disabled);
    return s == 2 && !disabled;
}

// ---- Tab 0: Display -----------------------------------------------------------------------------------------------------------------
void tab_display(const LiveStatus& live, Page& p, float bottom_h) {
    DisplaySettings& d = p.edit.display;
    extras::LatencySettings& l = p.edit.extras.latency;

    pane_begin("tab_display", bottom_h);

    card_group("窗口与分辨率", "Window & Resolution");
    int wmode = window_mode_index(d.window_mode);
    if (card_choice("wmode", "显示模式", "Window mode",
                    "无边框全屏可瞬间切换且支持 F11 / Alt+Enter 快捷切换；独占全屏会直接接管显示器。",
                    "Borderless fullscreen switches instantly (F11 / Alt+Enter). Exclusive takes over the display.",
                    &wmode, kWindowModeZh, kWindowModeEn, kWindowModeCount)) {
        d.window_mode = kWindowModeKeys[wmode];
        mark(p);
    }

    refresh_monitors(p);
    {
        std::vector<std::string> mons;
        mons.emplace_back(tr("自动 (当前窗口所在显示器)", "Auto (current display)"));
        for (const std::string& m : p.monitors) mons.push_back(m);
        int mon = std::clamp(d.monitor, 0, static_cast<int>(mons.size()) - 1);
        if (card_choice_vec("mon", "目标显示器", "Monitor",
                            "选择窗口和全屏模式显示的物理显示器。",
                            "Choose which physical monitor to display the game on.",
                            &mon, mons)) {
            d.monitor = mon;
            mark(p);
        }
    }

    int preset = 3;   // default 2560x1440
    for (int i = 0; i < kSizePresetCount; ++i)
        if (kSizePresets[i][0] == d.width && kSizePresets[i][1] == d.height) preset = i;
    if (card_choice("wsize", "窗口分辨率", "Window size",
                    "窗口模式下的画面尺寸。在无边框全屏时，窗口会填满桌面，退出全屏后恢复此尺寸。",
                    "Window size in windowed mode. Restored when leaving fullscreen.",
                    &preset, kSizeLabels, kSizeLabels, kSizePresetCount)) {
        d.width = kSizePresets[preset][0];
        d.height = kSizePresets[preset][1];
        mark(p);
    }

    if (live.width > 0 && (live.width != d.width || live.height != d.height)) {
        char cur_sz[48];
        std::snprintf(cur_sz, sizeof cur_sz, "%d x %d", live.width, live.height);
        if (card_button("use_cur_sz", "使用当前窗口尺寸", "Use current window size",
                        "把当前实际窗口宽高直接填入上面的窗口分辨率设置。",
                        "Copy the current window dimensions into the setting above.", cur_sz)) {
            d.width = live.width;
            d.height = live.height;
            mark(p);
        }
    }

    if (card_toggle("keep_ar", "保持 16:9 画面比例", "Keep 16:9 aspect ratio",
                    "在非 16:9 屏幕上两侧/上下留黑边，避免人物画面被拉伸变形。",
                    "Letterbox / pillarbox on non-16:9 displays instead of stretching.", &d.keep_aspect)) {
        mark(p);
    }

    card_group("帧率与同步", "Frame Rate & Sync");
    if (card_toggle("vsync", "垂直同步 (VSync)", "VSync",
                    "开启（推荐）：使用 FIFO 呈现模式，消除画面撕裂并防止 AMD 显卡交换链竞态。关闭：使用 Immediate 模式以获得最低延迟。",
                    "On (recommended on AMD): FIFO presentation prevents tearing and swapchain races. Off: lowest latency.",
                    &d.vsync)) {
        mark(p);
    }

    {
        int fidx = 0;
        for (int i = 0; i < kFpsChoiceCount; ++i)
            if (kFpsChoices[i] == d.fps_cap) fidx = i;
        std::vector<std::string> flabels;
        flabels.reserve(kFpsChoiceCount);
        for (int i = 0; i < kFpsChoiceCount; ++i) {
            char b[48];
            fps_label_text(kFpsChoices[i], b, sizeof b);
            flabels.emplace_back(b);
        }
        if (card_choice_vec("fps_cap", "帧率上限", "Frame limit",
                            "限制游戏运行帧率。60 fps 配合垂直同步最稳定；使用 VRR (FreeSync/G-Sync) 可点下方按钮一键设为略低于刷新率。",
                            "Caps the frame rate. 60 fps with VSync is smoothest; VRR users can cap just below refresh rate.",
                            &fidx, flabels)) {
            d.fps_cap = kFpsChoices[fidx];
            mark(p);
        }
    }

    if (live.refresh_hz > 0.0f) {
        char vrr[48];
        const int cap = static_cast<int>(std::floor(nxrt::suggest_vrr_cap(live.refresh_hz)));
        std::snprintf(vrr, sizeof vrr, "%d fps", cap);
        if (card_button("vrr_cap", "一键设为 VRR 最佳上限", "Set VRR-friendly cap",
                        "根据当前显示器刷新率自动设为略低于刷新率的帧数上限，配合 FreeSync / G-Sync 减少输入延迟。",
                        "Automatically sets the cap slightly below display refresh rate for FreeSync / G-Sync.", vrr)) {
            d.fps_cap = cap;
            mark(p);
        }
    }

    card_group("低延迟", "Low Latency");
    int lmode = static_cast<int>(l.mode);
    if (card_choice("lat_mode", "低延迟模式 (Anti-Lag 2 / Reflex)", "Low latency mode",
                    "启用 AMD Anti-Lag 2 或 NVIDIA Reflex 降低从手柄/键鼠输入到屏幕显示的延迟。",
                    "Reduces input-to-display latency via AMD Anti-Lag 2 or NVIDIA Reflex.",
                    &lmode, kLatencyZh, kLatencyEn, 4, true)) {
        l.mode = static_cast<extras::LatencyMode>(lmode);
        mark(p);
    }
    if (card_slider_i("lat_ahead", "预渲染帧数上限", "Frames ahead",
                      "低延迟开启时允许提前排队的帧数。-1 为不限制，1 兼顾流畅与延迟，0 延迟最低但可能略降帧率。",
                      "Maximum frames queued ahead when low latency is active (-1 = unlimited).",
                      &l.frames_ahead, -1, 3, 1, "%d", true, false, tr("不限制", "No limit"))) {
        mark(p);
    }

    pane_end(live);
}

// ---- Tab 1: Graphics ----------------------------------------------------------------------------------------------------------------
void tab_graphics(const LiveStatus& live, Page& p, float bottom_h) {
    DisplaySettings& d = p.edit.display;
    extras::PictureSettings& pic = p.edit.extras.picture;
    extras::HdrSettings& hdr = p.edit.extras.hdr;
    extras::UpscaleSettings& up = p.edit.extras.upscale;

    pane_begin("tab_graphics", bottom_h);

    card_group("画面色调 (拖动实时生效)", "Colour Grading (Live)");
    if (card_button("pic_neutral", "恢复原版色调", "Preset: Neutral",
                    "将对比度、饱和度、黑位、伽马恢复为游戏原始输出，实时生效。",
                    "Resets contrast, saturation, black level and gamma to untouched game output.",
                    pic.neutral() ? tr("当前", "Active") : "")) {
        if (extras::picture_preset("neutral", &pic)) {
            extras::set_picture_live(pic);
            mark(p);
        }
    }
    if (card_button("pic_vivid", "鲜艳通透预设", "Preset: Vivid",
                    "适度提升通透度：对比度 1.10、饱和度 1.15、黑位 -0.03，可有效消除画面灰蒙感，实时生效。",
                    "Modest boost: contrast 1.10, saturation 1.15, black level -0.03. Live preview.")) {
        if (extras::picture_preset("vivid", &pic)) {
            extras::set_picture_live(pic);
            mark(p);
        }
    }
    if (card_slider_f("pic_con", "对比度", "Contrast",
                      "拉大明暗反差。1.00 为游戏原版默认值，修改时画面实时变化。",
                      "Spreads tones from mid-grey; 1.00 is untouched. Applies live.",
                      &pic.contrast, 0.50, 1.50, 0.02, "%.2f", false, true)) {
        extras::set_picture_live(pic);
        mark(p);
    }
    if (card_slider_f("pic_sat", "饱和度", "Saturation",
                      "调整画面色彩鲜艳程度。0.00 为黑白，1.00 为原版，推荐 1.00~1.20。",
                      "Colour intensity; 1.00 is untouched. Applies live.",
                      &pic.saturation, 0.00, 2.00, 0.05, "%.2f", false, true)) {
        extras::set_picture_live(pic);
        mark(p);
    }
    if (card_slider_f("pic_blk", "黑位调整", "Black level",
                      "设为负值（如 -0.03）可压暗发灰的暗部，让夜景和阴影更通透；0.00 为原版。",
                      "Negative pulls hazy shadows toward pure black; 0.00 is untouched.",
                      &pic.black, -0.25, 0.25, 0.01, "%+.2f", false, true)) {
        extras::set_picture_live(pic);
        mark(p);
    }
    if (card_slider_f("pic_gam", "伽马亮度", "Gamma",
                      "调整中间调亮度：大于 1.00 画面更亮，小于 1.00 更暗，不影响纯黑和纯白。",
                      "Mid-tone brightness; 1.00 is untouched.",
                      &pic.gamma, 0.50, 2.00, 0.05, "%.2f", false, true)) {
        extras::set_picture_live(pic);
        mark(p);
    }

    card_group("贴图与渲染优化", "Textures & Rendering");
    int aniso = 0;
    for (int i = 0; i < kAnisoCount; ++i)
        if (kAnisoValues[i] == d.anisotropy) aniso = i;
    if (card_choice("aniso", "各向异性过滤", "Anisotropic filtering",
                    "大幅提升地面、石板和远景斜向贴图的清晰度，几乎无性能损耗（推荐 8x 或 16x）。",
                    "Sharpens angled ground and distant textures at almost zero GPU cost (8x/16x recommended).",
                    &aniso, kAnisoZh, kAnisoEn, kAnisoCount)) {
        d.anisotropy = kAnisoValues[aniso];
        mark(p);
    }
    if (card_slider_f("lod_bias", "贴图 LOD 偏移", "Texture LOD bias",
                      "负值（如 -0.50）会优先选用更清晰的贴图细节，正值更柔和。原生 1440p 下 0.00 ~ -0.50 最佳。",
                      "Negative values select sharper mip levels; 0.00 to -0.50 is ideal at 1440p.",
                      &d.lod_bias, -2.0, 2.0, 0.25, "%+.2f")) {
        mark(p);
    }
    int astc = 1;
    for (int i = 0; i < kAstcCount; ++i)
        if (d.astc_quality == kAstcValues[i]) astc = i;
    if (card_choice("astc", "ASTC 贴图转码质量", "ASTC texture quality",
                    "PC 显卡不支持主机 ASTC 压缩，需转码为 BC7。「高质量」会在后台精编并缓存到磁盘，画质与显存最均衡。",
                    "Converts Switch ASTC textures to BC7. High re-encodes cleanly in background and caches to disk.",
                    &astc, kAstcZh, kAstcEn, kAstcCount, true)) {
        d.astc_quality = kAstcValues[astc];
        mark(p);
    }
    if (card_toggle("dynres", "游戏动态分辨率", "Dynamic resolution",
                    "关闭（推荐）：保持当前真原生 2560x1440 清晰度不降分辨率。开启后由游戏根据负载缩放。",
                    "Off keeps fixed native 2560x1440 sharpness without downscaling.", &d.dynamic_resolution)) {
        mark(p);
    }
    if (card_toggle("prewarm", "后台着色器预热", "Shader pipeline prewarm",
                    "启动时在后台提前编译历史记录的渲染管线，大幅减少跑图进新区域时的首次编译卡顿。",
                    "Precompiles previously seen pipelines on background threads to reduce area-load stutter.",
                    &d.shader_prewarm, true)) {
        mark(p);
    }
    if (card_toggle("fast_vram", "显存镜像加速", "Faster GPU memory",
                    "在独立显存保留常用缓冲副本（需额外最多 2 GiB 显存）。nxrt.ini 中的 [nvn] 设置优先于此项。",
                    "Keeps device-local copies of frequently read buffers. [nvn] in nxrt.ini takes priority.",
                    &d.fast_gpu_memory, true)) {
        mark(p);
    }
    if (card_toggle("barriers", "精简管线屏障", "Fewer GPU waits",
                    "AMD 显卡建议保持关闭（使用完整屏障防花屏）。注意：当前 nxrt.ini 已固定开启完整屏障以保证稳定性。",
                    "Recommended off on AMD GPUs for stability. Note: nxrt.ini pass_barriers overrides this.",
                    &d.fewer_gpu_waits, true)) {
        mark(p);
    }

    card_group("超分与锐化", "Upscaling & Sharpening");
    {
        int uidx = 0;
        for (int i = 0; i < kUpscaleOrderCount; ++i)
            if (kUpscaleOrder[i] == up.mode) uidx = i;
        std::vector<std::string> unames;
        unames.reserve(kUpscaleOrderCount);
        for (int i = 0; i < kUpscaleOrderCount; ++i) {
            const int m = static_cast<int>(kUpscaleOrder[i]);
            std::string s = g_zh ? kUpscaleZh[m] : kUpscaleEn[m];
            if (!upscale_available(kUpscaleOrder[i])) s += tr(" (不可用)", " (N/A)");
            unames.push_back(std::move(s));
        }
        if (card_choice_vec("up_mode", "输出超分/锐化器", "Output upscaler",
                            "用于将渲染画面缩放至窗口尺寸（FSR 1 / NIS 为空间锐化；游戏内 3D 通道当前通过 nxrt.ini 以原生 1440p 1:1 直出）。",
                            "Upscales or sharpens the output image. Note: 3D native 1440p is controlled via nxrt.ini.",
                            &uidx, unames)) {
            if (upscale_available(kUpscaleOrder[uidx])) {
                up.mode = kUpscaleOrder[uidx];
                mark(p);
            }
        }
    }
    if (up.mode == extras::UpscaleMode::Fsr3 || up.mode == extras::UpscaleMode::Dlss) {
        int q = static_cast<int>(up.quality);
        if (card_choice("up_qual", "超分质量档位", "Upscale quality",
                        "控制内部 3D 场景缩放比例，原生抗锯齿 (100%) 最清晰。",
                        "Controls internal render percentage; Native AA (100%) is sharpest.",
                        &q, kUpscaleQualZh, kUpscaleQualEn, 6)) {
            up.quality = static_cast<extras::UpscaleQuality>(q);
            mark(p);
        }
    }
    if (card_slider_f("up_sharp", "画面锐度", "Sharpness",
                      "调整 FSR / NIS 的锐化强度（0.00 关闭，1.00 最强，推荐 0.40 ~ 0.60）。",
                      "Sharpening strength for FSR / NIS (0.00 off, 1.00 max).",
                      &up.sharpness, 0.0, 1.0, 0.05, "%.2f")) {
        mark(p);
    }

    card_group("HDR 高动态范围输出", "HDR Output");
    int hmode = static_cast<int>(hdr.mode);
    if (card_choice("hdr_mode", "HDR 模式", "HDR mode",
                    "开启需显示器及 Windows 系统均开启 HDR。「Switch 2 原生 HDR」使用游戏原版 HDR 色调映射参数。",
                    "Requires an HDR display with Windows HDR enabled.",
                    &hmode, kHdrModeZh, kHdrModeEn, 4, true)) {
        hdr.mode = static_cast<extras::HdrMode>(hmode);
        mark(p);
    }
    int hfmt = static_cast<int>(hdr.format);
    if (card_choice("hdr_fmt", "HDR 信号格式", "HDR format",
                    "发送给显示器的信号格式：HDR10 或 scRGB，自动会优先选用显示器原生支持的 HDR10。",
                    "Signal format sent to display (HDR10 or scRGB).",
                    &hfmt, kHdrFmtZh, kHdrFmtEn, 3, true)) {
        hdr.format = static_cast<extras::HdrFormat>(hfmt);
        mark(p);
    }
    int peak = static_cast<int>(std::lround(hdr.peak_nits));
    if (card_slider_i("hdr_peak", "HDR 峰值亮度", "HDR peak brightness",
                      "高光能达到的最大亮度（尼特），设为自动则直接读取显示器上报的峰值亮度。",
                      "Maximum highlight brightness in nits (Auto reads display capability).",
                      &peak, 0, 2000, 50, "%d nits", false, false, tr("自动", "Auto"), 200)) {
        hdr.peak_nits = peak;
        mark(p);
    }
    int paper = static_cast<int>(std::lround(hdr.paper_white_nits));
    if (card_slider_i("hdr_paper", "HDR 纸白亮度", "HDR paper white",
                      "普通白色与 UI 的亮度（尼特），自动会跟随 Windows SDR 内容亮度设置。",
                      "Standard white & UI luminance in nits.",
                      &paper, 0, 500, 10, "%d nits", false, false, tr("自动", "Auto"), 80)) {
        hdr.paper_white_nits = paper;
        mark(p);
    }
    if (card_slider_f("hdr_boost", "HDR 高光增强", "HDR highlight boost",
                      "控制高光向峰值亮度扩展的幅度，0.00 接近 SDR，1.00 标准 HDR。",
                      "Expands highlights toward peak brightness.",
                      &hdr.highlight_boost, 0.0, 2.0, 0.10, "%.2f")) {
        mark(p);
    }

    pane_end(live);
}

// ---- Tab 2: Audio -------------------------------------------------------------------------------------------------------------------
void tab_audio(const LiveStatus& live, Page& p, float bottom_h) {
    AudioSettings& a = p.edit.audio;
    if (!p.audio_loaded) load_audio_devices(p);

    pane_begin("tab_audio", bottom_h);

    card_group("音量控制", "Volume");
    int vol_pct = static_cast<int>(std::lround(a.volume * 100.0));
    if (card_slider_i("vol", "主音量", "Master volume",
                      "控制游戏整体输出音量（0% 静音 ~ 100% 满音量）。",
                      "Master audio output gain (0% to 100%).",
                      &vol_pct, 0, 100, 5, "%d%%")) {
        a.volume = std::clamp(vol_pct, 0, 100) / 100.0;
        mark(p);
    }
    if (card_toggle("mute_bg", "切出窗口时自动静音", "Mute when unfocused",
                    "当你 Alt+Tab 切换到桌面或其他软件时自动静音，切回游戏自动恢复。",
                    "Automatically mutes game audio when the window loses focus.", &a.mute_unfocused)) {
        mark(p);
    }

    card_group("输出设备", "Output Device");
    {
        std::vector<std::string> devs;
        devs.emplace_back(tr("系统默认设备", "System default"));
        int cur = 0;
        for (std::size_t i = 0; i < p.audio_devices.size(); ++i) {
            devs.push_back(p.audio_devices[i]);
            if (a.device == p.audio_devices[i]) cur = static_cast<int>(i) + 1;
        }
        if (card_choice_vec("adev", "音频输出设备", "Output device",
                            "选择播放游戏声音的扬声器或耳机设备。更改输出设备需重启游戏生效。",
                            "Selects the audio output device (takes effect on next launch).",
                            &cur, devs, true)) {
            a.device = cur == 0 ? "default" : p.audio_devices[static_cast<std::size_t>(cur - 1)];
            mark(p);
        }
    }
    {
        char cnt[48];
        std::snprintf(cnt, sizeof cnt, tr("共 %d 个设备", "%d devices"), static_cast<int>(p.audio_devices.size()));
        if (card_button("refresh_audio", "刷新音频设备列表", "Refresh audio devices",
                        "如果刚插入耳机或切换了声卡，点击此项重新扫描可用输出设备。",
                        "Rescans available Windows audio output devices.", cnt)) {
            load_audio_devices(p);
            set_notice(p, tr("音频设备列表已刷新", "Audio device list refreshed"), false);
        }
    }

    pane_end(live);
}

// ---- Tab 3: Controls ----------------------------------------------------------------------------------------------------------------
void tab_controls(UiHost& host, const LiveStatus& live, Page& p, float bottom_h) {
    PadSettings& pad = p.edit.pad;
    MouseSettings& m = p.edit.mouse;

    pane_begin("tab_controls", bottom_h);

    card_group("按键提示与手柄布局", "Prompts & Gamepad Layout");
    int pstyle = static_cast<int>(p.edit.prompts.style);
    if (card_choice("prompts", "游戏内按键图标风格", "Button prompt icons",
                    "切换界面上显示的按键图标（Switch / Xbox / PlayStation / 键鼠 / 自动跟随最近使用的设备）。",
                    "Chooses which button icons the game displays.",
                    &pstyle, kPromptZh, kPromptEn, kPromptStyleCount)) {
        p.edit.prompts.style = static_cast<PromptStyle>(pstyle);
        mark(p);
    }
    if (card_toggle("abxy_lbl", "按键按标识映射 (Xbox A = Switch A)", "Buttons by label (A=A)",
                    "开启：Xbox 手柄下键 A 对应 Switch A（确认）。关闭：按任天堂物理位置，右键 B 对应 Switch A（确认）。",
                    "On: Xbox bottom A acts as Switch A. Off: Nintendo positional layout (east button = Switch A).",
                    &pad.label_abxy)) {
        mark(p);
    }

    card_group("手柄摇杆、震动与陀螺仪", "Sticks, Rumble & Gyro");
    if (card_slider_f("ls_dz", "左摇杆死区", "Left stick dead zone",
                      "过滤左摇杆中心轻微漂移，数值越大需要推得越远才开始移动。",
                      "Filters minor left-stick drift near centre.", &pad.stick_deadzone, 0.0, 0.50, 0.02, "%.2f")) {
        mark(p);
    }
    if (card_slider_f("rs_dz", "右摇杆死区", "Right stick dead zone",
                      "过滤右摇杆（视角转动）的中心漂移。",
                      "Filters minor right-stick drift near centre.", &pad.right_deadzone, 0.0, 0.50, 0.02, "%.2f")) {
        mark(p);
    }
    if (card_slider_f("ls_max", "左摇杆满行程阈值", "Left stick max range",
                      "如果某些手柄推满仍无法全速奔跑，可适当调低此值（如 0.90）。",
                      "Lower if your stick does not reach 100% run speed at full deflection.", &pad.stick_max, 0.50, 1.00, 0.05, "%.2f")) {
        mark(p);
    }
    if (card_slider_f("look_s", "右摇杆视角灵敏度", "Look sensitivity",
                      "控制手柄右摇杆旋转镜头的速度倍率。",
                      "Multiplier for right-stick camera rotation speed.", &pad.look_sens, 0.25, 3.00, 0.05, "%.2fx")) {
        mark(p);
    }
    if (card_toggle("pad_invy", "反转手柄垂直视角", "Invert right-stick Y",
                    "开启后右摇杆向上推会向下看。",
                    "Pushing right stick up looks down.", &pad.invert_y)) {
        mark(p);
    }
    if (card_slider_f("trig_th", "扳机触发阈值", "Trigger threshold",
                      "模拟扳机 (LT/RT) 按下多少比例后判定为 Switch 的 ZL/ZR 按下。",
                      "How far analog triggers must be pressed to register ZL/ZR.", &pad.trigger_threshold, 0.05, 1.00, 0.05, "%.2f")) {
        mark(p);
    }
    if (card_toggle("rumble", "手柄震动反馈", "Controller rumble",
                    "开启或关闭游戏内的手柄震动反馈。",
                    "Enables or disables gamepad vibration.", &pad.rumble)) {
        mark(p);
    }
    if (card_slider_f("rumble_s", "震动强度", "Rumble strength",
                      "调整手柄震动的整体强弱（1.00 为默认强度）。",
                      "Scales gamepad vibration intensity.", &pad.rumble_scale, 0.0, 2.0, 0.10, "%.2fx")) {
        mark(p);
    }
    if (card_toggle("gyro", "六轴陀螺仪体感", "Gyro motion sensor",
                    "启用支持陀螺仪的手柄（Switch Pro / DualSense 等）体感输入。",
                    "Enables six-axis gyro input on supported controllers.", &pad.gyro)) {
        mark(p);
    }
    if (card_slider_f("gyro_s", "陀螺仪灵敏度", "Gyro scale",
                      "调整陀螺仪体感微调的灵敏度倍率。",
                      "Multiplier for gyro motion sensitivity.", &pad.gyro_scale, 0.1, 4.0, 0.1, "%.2fx")) {
        mark(p);
    }

    card_group("键鼠控制", "Mouse & Keyboard");
    double ms_x = source_sens(m.yaw_rad);
    if (card_slider_f("ms_x", "鼠标水平灵敏度", "Mouse horizontal sensitivity",
                      "键鼠操作时的水平镜头转动灵敏度。",
                      "Horizontal mouse look sensitivity.", &ms_x, 0.2, 10.0, 0.2, "%.2f")) {
        m.yaw_rad = rad_per_count(ms_x);
        if (p.link_pitch) m.pitch_rad = m.yaw_rad;
        mark(p);
    }
    double ms_y = source_sens(m.pitch_rad);
    if (card_slider_f("ms_y", "鼠标垂直灵敏度", "Mouse vertical sensitivity",
                      "键鼠操作时的垂直镜头转动灵敏度。",
                      "Vertical mouse look sensitivity.", &ms_y, 0.2, 10.0, 0.2, "%.2f")) {
        m.pitch_rad = rad_per_count(ms_y);
        mark(p);
    }
    if (card_toggle("ms_invy", "反转鼠标垂直方向", "Invert mouse Y",
                    "开启后鼠标向上移时视角向下看。",
                    "Inverts vertical mouse movement.", &m.invert_y)) {
        mark(p);
    }
    if (card_toggle("ms_menu", "菜单内显示鼠标指针", "Mouse cursor in menus",
                    "允许在游戏内菜单使用鼠标悬停与点击。",
                    "Enables mouse pointer hover and click inside game menus.", &m.menu_cursor)) {
        mark(p);
    }

    // Collapsible advanced remapping & live status (keeps main card list super clean)
    ImGui::Spacing();
    if (ImGui::CollapsingHeader(tr("高级：自定义手柄按键映射", "Advanced: Gamepad Button Remap"))) {
        if (ImGui::BeginTable("pad_remap_tbl", 2, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg)) {
            ImGui::TableSetupColumn(tr("物理按键", "Controller"));
            ImGui::TableSetupColumn(tr("映射为 Switch 按键", "Switch Button"));
            ImGui::TableHeadersRow();
            for (int i = 0; i < kPadSrcCount; ++i) {
                uint64_t& v = pad.remap[i];
                const int sel = pad_choice_of(v);
                ImGui::PushID(i);
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                ImGui::TextUnformatted(kPadSrcLabels[i]);
                ImGui::TableSetColumnIndex(1);
                ImGui::SetNextItemWidth(-FLT_MIN);
                if (ImGui::BeginCombo("##rm", sel >= 0 ? kPadChoiceNames[sel] : tr("自定义", "Custom"))) {
                    for (int c = 0; c < kPadChoiceCount; ++c) {
                        if (ImGui::Selectable(kPadChoiceNames[c], c == sel) && c != sel) {
                            v = pad_choice_value(c);
                            mark(p);
                        }
                    }
                    ImGui::EndCombo();
                }
                ImGui::PopID();
            }
            ImGui::EndTable();
        }
        if (ImGui::Button(tr("重置手柄按键映射", "Reset pad buttons"))) {
            for (uint64_t& v : pad.remap) v = kPadDefault;
            mark(p);
        }
    }

    if (ImGui::CollapsingHeader(tr("高级：键鼠按键绑定表", "Advanced: Keyboard & Mouse Bindings"))) {
        if (ImGui::BeginCombo(tr("场景上下文", "Context"), ctx_name(p.ctx))) {
            for (int c = 0; c < kCtxCount; ++c) {
                const Ctx ctx = static_cast<Ctx>(c);
                if (ImGui::Selectable(ctx_name(ctx), ctx == p.ctx) && ctx != p.ctx) {
                    stop_rebind(host, p);
                    p.ctx = ctx;
                }
            }
            ImGui::EndCombo();
        }
        int remove = -1;
        if (ImGui::BeginTable("kb_binds", 4, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg | ImGuiTableFlags_ScrollY,
                              ImVec2(0.0f, px(220.0f)))) {
            ImGui::TableSetupColumn(tr("按键", "Input"));
            ImGui::TableSetupColumn(tr("动作", "Action"));
            ImGui::TableSetupColumn(tr("触发", "Trigger"), ImGuiTableColumnFlags_WidthFixed, px(90.0f));
            ImGui::TableSetupColumn("##del", ImGuiTableColumnFlags_WidthFixed, px(32.0f));
            ImGui::TableHeadersRow();
            for (std::size_t i = 0; i < p.edit.bindings.size(); ++i) {
                Binding& b = p.edit.bindings[i];
                if (b.ctx != p.ctx) continue;
                const int row = static_cast<int>(i);
                ImGui::PushID(row);
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                const bool waiting = p.rebind == row;
                std::string blbl = waiting ? tr("请按键...", "press key...")
                                           : (b.in.kind == InKind::None ? "<none>" : input_name(b.in));
                blbl += "##bin";
                if (waiting) ImGui::PushStyleColor(ImGuiCol_Button, kPressed);
                if (ImGui::Button(blbl.c_str(), ImVec2(-FLT_MIN, 0.0f))) {
                    stop_fps_capture(host, p);
                    p.rebind = row;
                    host.begin_capture();
                }
                if (waiting) ImGui::PopStyleColor();
                ImGui::TableSetColumnIndex(1);
                ImGui::SetNextItemWidth(-FLT_MIN);
                if (ImGui::BeginCombo("##act", act_label(b.act))) {
                    for (int a = 0; a < kActCount; ++a) {
                        const Act act = static_cast<Act>(a);
                        if (ImGui::Selectable(act_label(act), act == b.act) && act != b.act) {
                            b.act = act;
                            mark(p);
                        }
                    }
                    ImGui::EndCombo();
                }
                ImGui::TableSetColumnIndex(2);
                ImGui::SetNextItemWidth(-FLT_MIN);
                if (ImGui::BeginCombo("##trg", trig_name(b.trig))) {
                    for (Trig t : kTrigChoices) {
                        if (ImGui::Selectable(trig_name(t), t == b.trig) && t != b.trig) {
                            b.trig = t;
                            mark(p);
                        }
                    }
                    ImGui::EndCombo();
                }
                ImGui::TableSetColumnIndex(3);
                if (ImGui::SmallButton("x")) remove = row;
                ImGui::PopID();
            }
            ImGui::EndTable();
        }
        if (remove >= 0) {
            if (p.rebind == remove) stop_rebind(host, p);
            else if (p.rebind > remove) --p.rebind;
            p.edit.bindings.erase(p.edit.bindings.begin() + remove);
            mark(p);
        }
        if (ImGui::Button(tr("添加绑定", "Add binding"))) {
            Binding b;
            b.ctx = p.ctx;
            b.act = Act::Primary;
            b.trig = Trig::Press;
            p.edit.bindings.push_back(b);
            stop_fps_capture(host, p);
            p.rebind = static_cast<int>(p.edit.bindings.size()) - 1;
            host.begin_capture();
            mark(p);
        }
    }

    if (ImGui::CollapsingHeader(tr("实时手柄/输入状态测试", "Live Switch Pad Monitor"))) {
        for (int i = 0; i < kSwitchButtonCount; ++i) {
            const bool on = (live.out.buttons & hid::btn(kSwitchButtons[i].bit)) != 0;
            ImGui::PushID(i);
            ImGui::PushStyleColor(ImGuiCol_Button, on ? kPressed : kReleased);
            ImGui::Button(kSwitchButtons[i].name, ImVec2(px(58.0f), 0.0f));
            ImGui::PopStyleColor();
            ImGui::PopID();
            if (i % 8 != 7) ImGui::SameLine();
        }
        ImGui::Text("LS (%.2f, %.2f)   RS (%.2f, %.2f)", live.out.lx, live.out.ly, live.out.rx, live.out.ry);
    }

    pane_end(live);
}

// ---- Tab 4: Overlay, Hotkeys & Language ---------------------------------------------------------------------------------------------
void tab_overlay(UiHost& host, const LiveStatus& live, Page& p, float bottom_h) {
    const FpsSettings fps = host.settings().fps;

    pane_begin("tab_overlay", bottom_h);

    card_group("帧率与性能监控 (实时生效)", "Performance Overlay (Live)");
    bool show = fps.show;
    if (card_toggle("fps_show", "显示帧率监控", "Show FPS counter",
                    "在屏幕角落实时显示当前帧率，也可随时按 F10 开关。",
                    "Shows a live frame rate counter in the corner (hotkey F10).", &show, false, true)) {
        FpsSettings f = fps;
        f.show = show;
        set_fps_live(host, f);
    }

    int corner = static_cast<int>(fps.corner);
    if (card_choice("fps_corner", "监控显示位置", "Overlay corner",
                    "选择帧率监控卡片停靠在屏幕的哪一个角落。",
                    "Selects which corner displays the FPS counter.",
                    &corner, kCornerZh, kCornerEn, kCornerCount, false, true)) {
        FpsSettings f = fps;
        f.corner = static_cast<Corner>(corner);
        set_fps_live(host, f);
    }

    int detail = std::clamp(fps.detail, 0, kFpsDetailCount - 1);
    if (card_choice("fps_detail", "监控信息详细度", "Counter detail",
                    "可选择仅显示 FPS、显示 FPS + 帧时间(ms)，或额外显示 1% Low 与最慢帧耗时。",
                    "Controls how much timing detail is shown in the overlay.",
                    &detail, kFpsDetailZh, kFpsDetailEn, kFpsDetailCount, false, true)) {
        FpsSettings f = fps;
        f.detail = detail;
        set_fps_live(host, f);
    }

    bool in_shots = fps.in_screenshots;
    if (card_toggle("fps_shots", "截图时包含帧率监控", "Include counter in screenshots",
                    "关闭（推荐）：按 F12 截图时会保存纯净无遮挡的游戏画面。",
                    "Off (recommended) keeps F12 screenshots clean without the FPS counter.", &in_shots, false, true)) {
        FpsSettings f = fps;
        f.in_screenshots = in_shots;
        set_fps_live(host, f);
    }

    {
        const std::string key = input_name(fps.key);
        const char* right = p.fps_capture ? tr("请按键盘按键...", "Press a key...") : (key.empty() ? "F10" : key.c_str());
        if (card_button("fps_key", "更改帧率监控快捷键", "Change FPS hotkey",
                        "点击后按任意键盘按键即可替换默认的 F10 帧率开关快捷键，按 Esc 取消。",
                        "Click and press any keyboard key to rebind the FPS overlay toggle.", right)) {
            stop_rebind(host, p);
            p.fps_capture = true;
            host.begin_capture();
        }
    }

    card_group("菜单外观与语言", "Menu & Language");
    {
        static const char* const kLangs[] = {"简体中文", "English"};
        int lang = g_zh ? 0 : 1;
        if (card_choice("menu_lang", "菜单界面语言", "Menu language",
                        "在简体中文与英文之间实时切换当前 F1 设置菜单的显示语言。",
                        "Switches the F1 settings menu between Simplified Chinese and English.",
                        &lang, kLangs, kLangs, 2, false, true)) {
            g_zh = (lang == 0);
        }
    }

    card_group("常用快捷键速查", "Hotkeys Reference");
    card_button("hk_f1", "打开 / 关闭系统设置菜单", "Toggle settings menu",
                "随时唤出或隐藏本设置菜单；菜单打开期间自动屏蔽游戏内按键输入，防止误操作。手柄按 - + + 也可呼出。",
                "Opens or closes this menu while blocking game input. Gamepad: Minus + Plus.", "F1 / Esc");
    card_button("hk_f10", "开关帧率性能监控", "Toggle FPS counter",
                "随时在右上角显示或隐藏实时帧率与帧时间监控。",
                "Toggles the live corner FPS overlay.", "F10");
    card_button("hk_f11", "切换全屏 / 窗口模式", "Toggle fullscreen",
                "在无边框全屏与窗口模式之间瞬间切换。",
                "Instantly toggles borderless fullscreen and windowed mode.", "F11 / Alt+Enter");
    card_button("hk_f12", "保存无损 PNG 截图", "Save PNG screenshot",
                "将当前原生高清画面保存为无损 PNG 到 xc2/build/boot/shots_manual/ 目录。",
                "Saves a lossless PNG screenshot into shots_manual/.", "F12");

    pane_end(live);
}

// ---- Tab bar helper -----------------------------------------------------------------------------------------------------------------
void draw_category_tabs(Page& p) {
    struct TabDef {
        const char* zh;
        const char* en;
    };
    static const TabDef kTabs[] = {
        {"显示", "Display"},
        {"画质", "Graphics"},
        {"音频", "Audio"},
        {"控制", "Controls"},
        {"界面与快捷键", "Overlay"},
    };
    constexpr int kTabCount = static_cast<int>(sizeof kTabs / sizeof kTabs[0]);

    const float total_w = ImGui::GetContentRegionAvail().x;
    const float gap = px(8.0f);
    const float btn_w = (total_w - gap * (kTabCount - 1)) / static_cast<float>(kTabCount);
    const float btn_h = px(38.0f);
    ImDrawList* dl = ImGui::GetWindowDrawList();

    for (int i = 0; i < kTabCount; ++i) {
        if (i > 0) ImGui::SameLine(0.0f, gap);
        const bool sel = (p.active_tab == i);
        const ImVec2 pos = ImGui::GetCursorScreenPos();
        ImGui::PushID(i);
        const bool clicked = ImGui::InvisibleButton("##cat_tab", ImVec2(btn_w, btn_h));
        const bool hov = ImGui::IsItemHovered();
        const bool foc = ImGui::IsItemFocused();
        ImGui::PopID();
        if (clicked) {
            p.active_tab = i;
            g_pane.shown.valid = false;
        }
        const ImU32 bg = sel ? IM_COL32(28, 86, 102, 235)
                             : (hov || foc) ? IM_COL32(24, 64, 82, 195) : IM_COL32(12, 24, 40, 175);
        dl->AddRectFilled(pos, ImVec2(pos.x + btn_w, pos.y + btn_h), bg, px(8.0f));
        if (sel) {
            dl->AddRect(pos, ImVec2(pos.x + btn_w, pos.y + btn_h), kColGold, px(8.0f), 0, 1.5f);
            dl->AddRectFilled(ImVec2(pos.x + px(14.0f), pos.y + btn_h - px(3.0f)),
                              ImVec2(pos.x + btn_w - px(14.0f), pos.y + btn_h), kColGold, px(2.0f));
        } else {
            dl->AddRect(pos, ImVec2(pos.x + btn_w, pos.y + btn_h), IM_COL32(65, 130, 150, 65), px(8.0f), 0, 1.0f);
        }
        const char* lbl = tr(kTabs[i].zh, kTabs[i].en);
        const ImVec2 ts = ImGui::CalcTextSize(lbl);
        dl->AddText(ImVec2(pos.x + (btn_w - ts.x) * 0.5f, pos.y + (btn_h - ts.y) * 0.5f),
                    sel ? kColGold : kColWhite, lbl);
    }

    // L1 / R1 gamepad shoulder buttons switch tabs cleanly
    if (ImGui::IsKeyPressed(ImGuiKey_GamepadL1, false)) {
        p.active_tab = (p.active_tab + kTabCount - 1) % kTabCount;
        g_pane.shown.valid = false;
    }
    if (ImGui::IsKeyPressed(ImGuiKey_GamepadR1, false)) {
        p.active_tab = (p.active_tab + 1) % kTabCount;
        g_pane.shown.valid = false;
    }
}

}  // namespace

void draw_settings_page(UiHost& host) {
    static Page page;
    Page& p = page;
    if (!p.loaded) {
        p.edit = host.settings();
        p.edit.fps = host.settings().fps;
        refresh_out_text(p);
        p.loaded = true;
    }
    poll_capture(host, p);
    const LiveStatus live = host.status();

    draw_category_tabs(p);
    ImGui::Dummy(ImVec2(0.0f, px(6.0f)));

    const float bottom_h = px(56.0f);
    switch (p.active_tab) {
        case 0: tab_display(live, p, bottom_h); break;
        case 1: tab_graphics(live, p, bottom_h); break;
        case 2: tab_audio(live, p, bottom_h); break;
        case 3: tab_controls(host, live, p, bottom_h); break;
        default: tab_overlay(host, live, p, bottom_h); break;
    }

    // Pinned bottom action bar
    ImGui::Separator();
    ImGui::Dummy(ImVec2(0.0f, px(3.0f)));

    if (p.dirty) {
        ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.14f, 0.50f, 0.46f, 1.0f));
        ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.18f, 0.64f, 0.58f, 1.0f));
    }
    if (ImGui::Button(tr("应用并保存", "Apply & Save"), ImVec2(px(138.0f), px(34.0f)))) apply_now(host, p);
    if (p.dirty) ImGui::PopStyleColor(2);

    ImGui::SameLine();
    if (ImGui::Button(tr("放弃修改", "Revert"), ImVec2(px(108.0f), px(34.0f)))) revert_to_saved(host, p);
    ImGui::SameLine();
    if (ImGui::Button(tr("恢复默认", "Defaults"), ImVec2(px(108.0f), px(34.0f)))) load_factory(host, p);

    ImGui::SameLine(0.0f, px(16.0f));
    if (host.capturing()) {
        ImGui::AlignTextToFramePadding();
        ImGui::TextColored(kGold, "%s", tr("请按下要绑定的按键，按 Esc 取消...", "Press a key to bind, Esc to cancel..."));
    } else if (p.dirty) {
        ImGui::AlignTextToFramePadding();
        ImGui::TextColored(kOrange, "%s", tr("● 有未保存的修改", "● Unsaved changes"));
    } else if (!p.notice.empty()) {
        ImGui::AlignTextToFramePadding();
        ImGui::TextColored(p.notice_warn ? kOrange : kEmerald, "%s", p.notice.c_str());
    } else {
        ImGui::AlignTextToFramePadding();
        ImGui::TextColored(kDimText, "%s", tr("提示：鼠标悬停或方向键选中条目，右侧查看说明", "Tip: hover or select an item for details"));
    }
}

void draw_settings_menu(UiHost& host, gfx::Overlay& ov) {
    static int last_frame = -2;
    const int frame = ImGui::GetFrameCount();
    const bool opened = frame != last_frame + 1;
    last_frame = frame;
    if (!opened && !host.capturing() && !ImGui::IsAnyItemActive() && !ImGui::IsPopupOpen("", ImGuiPopupFlags_AnyPopup) &&
        (ImGui::IsKeyPressed(ImGuiKey_Escape, false) || ImGui::IsKeyPressed(ImGuiKey_GamepadFaceRight, false))) {
        ov.request_hide();
    }

    const ImVec2 disp = ImGui::GetIO().DisplaySize;
    ImGui::GetBackgroundDrawList()->AddRectFilled(ImVec2(0.0f, 0.0f), disp, IM_COL32(3, 8, 16, 155));

    const float em = ImGui::GetFontSize();
    const float w = std::min(disp.x - 2.5f * em, std::max(54.0f * em, disp.x * 0.74f));
    const float h = std::min(disp.y - 2.5f * em, std::max(34.0f * em, disp.y * 0.82f));
    ImGui::SetNextWindowPos(ImVec2(disp.x * 0.5f, disp.y * 0.5f), ImGuiCond_Always, ImVec2(0.5f, 0.5f));
    ImGui::SetNextWindowSize(ImVec2(w, h), ImGuiCond_Always);
    if (opened) ImGui::SetNextWindowFocus();

    constexpr ImGuiWindowFlags kFlags = ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoCollapse |
                                        ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove;
    if (ImGui::Begin("##xc2_settings_modal", nullptr, kFlags)) {
        // Custom sleek top header bar
        ImGui::PushStyleColor(ImGuiCol_Text, kGold);
        ImGui::AlignTextToFramePadding();
        ImGui::TextUnformatted(tr("异度神剑 2  ·  系统设置", "Xenoblade Chronicles 2  ·  Settings"));
        ImGui::PopStyleColor();

        const float close_w = px(92.0f);
        const float lang_w = px(96.0f);
        const float right_x = ImGui::GetWindowContentRegionMax().x;
        ImGui::SameLine(std::max(px(260.0f), right_x - close_w - lang_w - px(10.0f)));
        if (ImGui::Button(g_zh ? "EN / 中文" : "中文 / EN", ImVec2(lang_w, 0.0f))) g_zh = !g_zh;
        ImGui::SameLine();
        if (ImGui::Button(tr("关闭 (F1)", "Close (F1)"), ImVec2(close_w, 0.0f))) ov.request_hide();

        ImGui::Dummy(ImVec2(0.0f, px(4.0f)));
        draw_settings_page(host);
    }
    ImGui::End();
}

}  // namespace nxrt::play
