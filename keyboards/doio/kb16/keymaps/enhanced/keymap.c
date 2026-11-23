// DOIO KB16 - VIA keymap that reports its layer to the PC.
//
// Every time the active layer changes, the pad taps Ctrl+Alt+Shift+F13
// for layer 1, Ctrl+Alt+Shift+F14 for layer 2 ... up to F20 for layer 8.
// AutoHotkey listens for those and sets its own Layer variable directly,
// so the PC and the pad can't drift apart.

#include QMK_KEYBOARD_H

#define NUM_LAYERS DYNAMIC_KEYMAP_LAYER_COUNT

enum custom_keycodes {
    // QK_USER_0 = 0x7E40. To re-assign it in VIA use the "Any" key and type 0x7E40.
    LYR_NEXT = QK_USER_0,  // layer knob, see "Layer knob + key handling" below
};

// Physical layout (knob presses are the 5th column):
//
//   [ k00 ][ k01 ][ k02 ][ k03 ]   (k04 left knob)  (k14 right knob)
//   [ k10 ][ k11 ][ k12 ][ k13 ]
//   [ k20 ][ k21 ][ k22 ][ k23 ]          (k24 big knob)
//   [ k30 ][ k31 ][ k32 ][ k33 ]
//
// If your left and right knob presses come out swapped after flashing,
// swap LYR_NEXT and KC_NO in the 5th column of row 0 and row 1.

// Top row sends Shift+F13..F16 instead of F9..F12, so the pad never sends
// keys your real keyboard also has (F11 = fullscreen, F12 = dev tools).
#define FKEY_LAYER                                                         \
    LAYOUT(S(KC_F13), S(KC_F14), S(KC_F15), S(KC_F16), _______,            \
           KC_F13, KC_F14, KC_F15, KC_F16, _______,        \
           KC_F17, KC_F18, KC_F19, KC_F20, _______,        \
           KC_F21, KC_F22, KC_F23, KC_F24)

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    // Layer 1: your current base layer
    [0] = LAYOUT(
        S(KC_F13), KC_MPRV, KC_MPLY, KC_MNXT, LYR_NEXT,  // top-left = info key
        KC_F13,  KC_F14,  KC_F15,  KC_CALC, KC_NO,     // right knob press is free now
        KC_F17,  KC_F18,  KC_F19,  KC_DEL,  KC_MUTE,   // big knob press: mute on every layer
        KC_HOME, KC_PGUP, KC_PGDN, KC_END
    ),
    // Layers 2-8: F9..F24. Knob presses fall through (_______) to layer 1.
    [1] = FKEY_LAYER,
    [2] = FKEY_LAYER,
    [3] = FKEY_LAYER,
    [4] = FKEY_LAYER,
    [5] = FKEY_LAYER,
    [6] = FKEY_LAYER,
    [7] = FKEY_LAYER,
};

#ifdef ENCODER_MAP_ENABLE
// Knob turns copied from your saved VIA layout (left turn, right turn).
// VIA macros were replaced with plain key combos that send the same keys,
// so they survive reflashing and stay editable in VIA.
// Encoder 0 / 1 are the two small knobs, encoder 2 is the big knob.
// Layers 5-8 are transparent, so their knobs act like layer 1.
#define WHEEL ENCODER_CCW_CW(MS_WHLD, MS_WHLU)
#define SAME  ENCODER_CCW_CW(_______, _______)
const uint16_t PROGMEM encoder_map[][NUM_ENCODERS][NUM_DIRECTIONS] = {
    //        encoder 0                                  encoder 1                           encoder 2 (big)
    [0] = { ENCODER_CCW_CW(KC_MRWD, KC_MFFD),         ENCODER_CCW_CW(KC_DOWN, KC_UP), ENCODER_CCW_CW(KC_VOLD, KC_VOLU) },                 // rewind/ff, arrows, volume
    [1] = { ENCODER_CCW_CW(S(KC_DOT), S(KC_COMM)),    WHEEL,                          ENCODER_CCW_CW(C(A(KC_MINS)), C(A(KC_EQL))) },     // > / <, scroll, per-app volume
    [2] = { ENCODER_CCW_CW(KC_J, KC_L),               WHEEL,                          ENCODER_CCW_CW(C(KC_Z), C(S(KC_Z))) },             // J/L, scroll, undo/redo
    [3] = { ENCODER_CCW_CW(KC_LBRC, KC_RBRC),         WHEEL,                          ENCODER_CCW_CW(C(KC_MINS), C(S(KC_EQL))) },        // [ / ], scroll, zoom out/in
    [4] = { SAME, SAME, SAME },
    [5] = { SAME, SAME, SAME },
    [6] = { SAME, SAME, SAME },
    [7] = { SAME, SAME, SAME },
};
#endif

// ---------- Per-layer lighting ----------
// Color + effect for each layer. Only effects that keep a single color are
// used, so the color always tells you the layer. Brightness is left alone,
// so VIA's brightness slider still works. (VIA's color/effect settings get
// overridden on every layer change.)

typedef struct {
    uint8_t mode, hue, sat, speed;
} layer_light_t;

static const layer_light_t layer_lights[8] = {
    { RGB_MATRIX_SOLID_COLOR,       28,  70,   0 },  // 1 warm white, solid
    { RGB_MATRIX_BREATHING,          4, 230,  60 },  // 2 coral, slow breathing
    { RGB_MATRIX_BAND_VAL,          28, 255,  70 },  // 3 amber, band sweep
    { RGB_MATRIX_BAND_SAT,          85, 240,  70 },  // 4 green, white band sweep
    { RGB_MATRIX_BREATHING,        125, 255,  60 },  // 5 teal, slow breathing
    { RGB_MATRIX_SOLID_COLOR,      160, 255,   0 },  // 6 blue, solid
    { RGB_MATRIX_BAND_PINWHEEL_VAL,195, 230,  70 },  // 7 violet, spinning pinwheel
    { RGB_MATRIX_SOLID_REACTIVE,   225, 200, 100 },  // 8 pink, solid + pressed keys flash
};

static void apply_layer_light(uint8_t layer) {
#ifdef RGB_MATRIX_ENABLE
    if (layer > 7) return;
    const layer_light_t *l = &layer_lights[layer];
    rgb_matrix_mode_noeeprom(l->mode);
    rgb_matrix_sethsv_noeeprom(l->hue, l->sat, rgb_matrix_get_val());
    if (l->speed) rgb_matrix_set_speed_noeeprom(l->speed);
#endif
}

// ---------- Knob labels for the OLED ----------
// The label is NOT written per knob. When a knob is turned or pressed, QMK
// looks up whatever key is assigned to it right now (from VIA's saved
// layout) and hands that key code to process_record_user. label_for()
// turns that key code into text. Remap a knob in VIA and the label follows,
// no reflash needed. Combos it doesn't know are spelled out, e.g. "C+S+F5".

static void append(char *buf, const char *s) {
    while (*buf) buf++;
    while (*s) *buf++ = *s++;
    *buf = 0;
}

static const char *named_combo(uint16_t kc) {
    switch (kc) {
        case C(KC_Z):            return "UNDO";
        case C(S(KC_Z)):
        case C(KC_Y):            return "REDO";
        case C(KC_X):            return "CUT";
        case C(KC_C):            return "COPY";
        case C(KC_V):            return "PASTE";
        case C(KC_S):            return "SAVE";
        case C(KC_EQL):
        case C(S(KC_EQL)):       return "ZOOM +";
        case C(KC_MINS):         return "ZOOM -";
        case C(A(KC_EQL)):       return "APP VOL +";
        case C(A(KC_MINS)):      return "APP VOL -";
        case C(KC_TAB):          return "NEXT TAB";
        case C(S(KC_TAB)):       return "PREV TAB";
        case S(KC_DOT):          return ">";
        case S(KC_COMM):         return "<";
        case KC_VOLU:            return "VOL +";
        case KC_VOLD:            return "VOL -";
        case KC_MUTE:            return "MUTE";
        case KC_MPLY:            return "PLAY/PAUSE";
        case KC_MNXT:            return "NEXT TRACK";
        case KC_MPRV:            return "PREV TRACK";
        case KC_MFFD:            return "FAST FWD";
        case KC_MRWD:            return "REWIND";
        case KC_BRIU:            return "BRIGHT +";
        case KC_BRID:            return "BRIGHT -";
        case MS_WHLU:            return "SCROLL UP";
        case MS_WHLD:            return "SCROLL DOWN";
        case MS_WHLL:            return "SCROLL LEFT";
        case MS_WHLR:            return "SCROLL RIGHT";
        case KC_UP:              return "UP";
        case KC_DOWN:            return "DOWN";
        case KC_LEFT:            return "LEFT";
        case KC_RGHT:            return "RIGHT";
        case KC_PGUP:            return "PAGE UP";
        case KC_PGDN:            return "PAGE DOWN";
        case KC_HOME:            return "HOME";
        case KC_END:             return "END";
        case KC_DEL:             return "DELETE";
        case KC_BSPC:            return "BACKSPACE";
        case KC_ENT:             return "ENTER";
        case KC_ESC:             return "ESC";
        case KC_TAB:             return "TAB";
        case KC_SPC:             return "SPACE";
        case KC_CALC:            return "CALC";
        case KC_NO:              return "";
    }
    return 0;
}

static const char *base_key_name(uint8_t k, char *tmp) {
    if (k >= KC_A && k <= KC_Z)  { tmp[0] = 'A' + (k - KC_A); tmp[1] = 0; return tmp; }
    if (k >= KC_1 && k <= KC_9)  { tmp[0] = '1' + (k - KC_1); tmp[1] = 0; return tmp; }
    if (k == KC_0)               return "0";
    if (k >= KC_F1 && k <= KC_F12) {
        uint8_t n = k - KC_F1 + 1; tmp[0] = 'F';
        if (n < 10) { tmp[1] = '0' + n; tmp[2] = 0; } else { tmp[1] = '1'; tmp[2] = '0' + n - 10; tmp[3] = 0; }
        return tmp;
    }
    if (k >= KC_F13 && k <= KC_F24) {
        uint8_t n = k - KC_F13 + 13; tmp[0] = 'F'; tmp[1] = '0' + n / 10; tmp[2] = '0' + n % 10; tmp[3] = 0;
        return tmp;
    }
    switch (k) {
        case KC_MINS: return "-";  case KC_EQL:  return "=";
        case KC_LBRC: return "[";  case KC_RBRC: return "]";
        case KC_BSLS: return "\\"; case KC_SCLN: return ";";
        case KC_QUOT: return "'";  case KC_GRV:  return "`";
        case KC_COMM: return ",";  case KC_DOT:  return ".";
        case KC_SLSH: return "/";
    }
    const char *named = named_combo(k);
    return named ? named : "?";
}

static void label_for(uint16_t kc, char *buf) {
    buf[0] = 0;
    const char *named = named_combo(kc);
    if (named) { append(buf, named); return; }

    if (kc >= QK_MACRO && kc <= QK_MACRO_MAX) {   // VIA macros: content isn't known here
        char n[4] = { 0 };
        uint8_t m = kc - QK_MACRO;
        if (m >= 10) { n[0] = '0' + m / 10; n[1] = '0' + m % 10; } else n[0] = '0' + m;
        append(buf, "MACRO "); append(buf, n);
        return;
    }
    if (kc >= QK_MODS && kc <= QK_MODS_MAX) {      // modifier combos, e.g. C+S+F5
        uint8_t mods = QK_MODS_GET_MODS(kc);
        if (mods & MOD_LCTL) append(buf, "C+");
        if (mods & MOD_LALT) append(buf, "A+");
        if (mods & MOD_LSFT) append(buf, "S+");
        if (mods & MOD_LGUI) append(buf, "WIN+");
        kc = QK_MODS_GET_BASIC_KEYCODE(kc);
    }
    if (kc <= 0xFF) {
        char tmp[4];
        append(buf, base_key_name(kc, tmp));
        return;
    }
    append(buf, "KEY");
}

// ---------- Layer knob + key handling ----------
//
// Left knob (LYR_NEXT):
//   tap ........................ next layer
//   hold + press key 1-8 ....... jump to that layer (top two rows, left to right)
//   hold + turn any knob ....... flip through layers (right = next, left = previous)
//   hold alone (0.4 s) ......... back to layer 1

static bool     announce_pending = true;  // also announce once after plugging in
static uint16_t boot_timer;
static uint16_t layer_key_timer;
static bool     layer_key_held;
static bool     layer_key_used;           // something happened during the hold
static uint16_t swallowed;                // keys whose press we ate; eat their release too

static char     knob_label[22];
static uint16_t knob_label_timer;
static bool     knob_label_active;
static bool     oled_dirty = true;

#define KNOB_LABEL_MS 1000

void keyboard_post_init_user(void) {
    boot_timer = timer_read();
    apply_layer_light(0);
}

// Called by QMK whenever the layer changes. Don't send keys from here
// (it can run mid-keypress); just flag it and send from the main loop.
layer_state_t layer_state_set_user(layer_state_t state) {
    announce_pending  = true;
    knob_label_active = false;  // show the new layer right away
    oled_dirty        = true;
    apply_layer_light(get_highest_layer(state | default_layer_state));
    return state;
}

void housekeeping_task_user(void) {
    if (knob_label_active && timer_elapsed(knob_label_timer) > KNOB_LABEL_MS) {
        knob_label_active = false;
        oled_dirty        = true;
    }

    // Wait a second after boot so the PC has finished setting the pad up.
    if (!announce_pending || timer_elapsed(boot_timer) < 1000) return;
    announce_pending = false;

    uint8_t layer = get_highest_layer(layer_state | default_layer_state);
    if (layer > 7) return;  // only F13..F20 are used for announcements
    tap_code16(C(A(S(KC_F13 + layer))));
}

static void show_knob_label(uint16_t keycode) {
    char buf[22];
    label_for(keycode, buf);
    if (!buf[0]) return;  // unassigned (KC_NO): nothing to show
    for (uint8_t i = 0; i < sizeof(knob_label); i++) knob_label[i] = buf[i];
    knob_label[sizeof(knob_label) - 1] = 0;
    knob_label_timer  = timer_read();
    knob_label_active = true;
    oled_dirty        = true;
}

static void go_to_layer(int8_t layer) {
    layer_move((uint8_t)((layer + NUM_LAYERS) % NUM_LAYERS));
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    keyevent_t e       = record->event;
    bool       is_knob = IS_ENCODEREVENT(e);
    uint8_t    current = get_highest_layer(layer_state);

    // The layer knob itself
    if (keycode == LYR_NEXT) {
        if (e.pressed) {
            layer_key_held  = true;
            layer_key_used  = false;
            layer_key_timer = timer_read();
        } else {
            layer_key_held = false;
            if (layer_key_used) {
                // jump / flip already happened
            } else if (timer_elapsed(layer_key_timer) >= LAYER_HOLD_MS) {
                go_to_layer(0);  // long press: back to layer 1 (also re-syncs AutoHotkey)
            } else {
                go_to_layer(current + 1);
            }
        }
        return false;
    }

    // While the layer knob is held: knob turns flip layers, keys 1-8 jump
    if (layer_key_held) {
        if (e.pressed) layer_key_used = true;  // any action during the hold cancels "back to layer 1"
        if (is_knob) {
            if (e.pressed) {
                layer_key_used = true;
                go_to_layer(e.key.row == KEYLOC_ENCODER_CW ? current + 1 : current - 1);
            }
            return false;
        }
        if (e.pressed && e.key.row < 2 && e.key.col < 4) {
            layer_key_used = true;
            swallowed |= 1u << (e.key.row * 4 + e.key.col);
            go_to_layer(e.key.row * 4 + e.key.col);
            return false;
        }
    }

    // Eat the release of a key whose press was used for a layer jump
    if (!e.pressed && !is_knob && e.key.row < 2 && e.key.col < 4) {
        uint16_t bit = 1u << (e.key.row * 4 + e.key.col);
        if (swallowed & bit) {
            swallowed &= ~bit;
            return false;
        }
    }

    // Normal knob use: show what it did on the OLED
    if (e.pressed && (is_knob || e.key.col == 4)) {
        show_knob_label(keycode);
    }
    return true;
}

// ---------- OLED ----------
// The boot logo is drawn as a raw image, so the screen must be cleared
// before text goes on; otherwise the logo stays underneath it.

#ifdef OLED_ENABLE
static void write_centered(uint8_t row, const char *text) {
    uint8_t len = 0;
    while (text[len] && len < 21) len++;
    oled_set_cursor((21 - len) / 2, row);
    for (uint8_t i = 0; i < len; i++) oled_write_char(text[i], false);
}

bool oled_task_user(void) {
    if (!oled_dirty) return false;  // only redraw when something changed
    oled_dirty = false;

    uint8_t layer = get_highest_layer(layer_state);
    char    tag[8] = "LAYER ";
    tag[6]         = '1' + layer;
    tag[7]         = 0;

    oled_clear();
    write_centered(1, knob_label_active ? knob_label : tag);
    return false;
}
#endif
