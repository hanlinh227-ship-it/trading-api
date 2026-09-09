from pathlib import Path

P=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
G=Path('signalhub-android/app/build.gradle')
M=Path('signalhub-android/app/src/main/AndroidManifest.xml')
s=P.read_text()
g=G.read_text()
m=M.read_text()

# Version
s=s.replace('private static final String APP_VERSION="3.17.0";','private static final String APP_VERSION="3.18.0";')
g=g.replace('versionCode 22','versionCode 23').replace("versionName '3.17.0'","versionName '3.18.0'")

# Imports needed for stable keyboard/search interaction.
s=s.replace('import android.content.Intent;\n','import android.content.Intent;\nimport android.content.Context;\n')
s=s.replace('import android.view.Gravity;\n','import android.view.Gravity;\nimport android.view.WindowManager;\nimport android.view.inputmethod.EditorInfo;\nimport android.view.inputmethod.InputMethodManager;\n')
s=s.replace('import android.widget.TextView;\n','import android.widget.TextView;\nimport android.text.Editable;\nimport android.text.TextWatcher;\nimport android.text.InputType;\n')

# Persistent Watchlist editor state. This prevents live refresh from destroying the EditText while typing.
s=s.replace('private final Map<String,Boolean> watchLoading=new ConcurrentHashMap<>();\n',
'''private final Map<String,Boolean> watchLoading=new ConcurrentHashMap<>();\n    private EditText watchSearchInput;\n    private LinearLayout watchSuggestions;\n''')

# Ensure the software keyboard can resize the Activity and remain visible.
s=s.replace('getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);',
'''getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);''')

# Do not rebuild the entire Watchlist while its text field owns focus.
s=s.replace('if(screen.equals("WATCH")&&System.currentTimeMillis()-watchLastRenderMs>2000){watchLastRenderMs=System.currentTimeMillis();renderWatchlist(false);}',
'''if(screen.equals("WATCH")&&!watchSearchHasFocus()&&System.currentTimeMillis()-watchLastRenderMs>2000){watchLastRenderMs=System.currentTimeMillis();renderWatchlist(false);}''')
s=s.replace('main.post(()->{if(screen.equals("WATCH"))renderWatchlist(false);});',
'''main.post(()->{if(screen.equals("WATCH")&&!watchSearchHasFocus())renderWatchlist(false);});''')

# Add robust search helpers immediately before watchPrefs().
needle='    private SharedPreferences watchPrefs(){return getSharedPreferences("signalhub_watch",MODE_PRIVATE);}'
helpers=r'''    private boolean watchSearchHasFocus(){return screen.equals("WATCH")&&watchSearchInput!=null&&watchSearchInput.hasFocus();}
    private void showWatchKeyboard(EditText input){
        if(input==null)return;input.setFocusable(true);input.setFocusableInTouchMode(true);input.requestFocus();input.setSelection(input.getText().length());
        main.postDelayed(()->{try{InputMethodManager imm=(InputMethodManager)getSystemService(Context.INPUT_METHOD_SERVICE);if(imm!=null)imm.showSoftInput(input,InputMethodManager.SHOW_IMPLICIT);}catch(Throwable ignored){}},80);
    }
    private void hideWatchKeyboard(){try{if(watchSearchInput!=null){InputMethodManager imm=(InputMethodManager)getSystemService(Context.INPUT_METHOD_SERVICE);if(imm!=null)imm.hideSoftInputFromWindow(watchSearchInput.getWindowToken(),0);watchSearchInput.clearFocus();}}catch(Throwable ignored){}}
    private String watchQuery(String raw){return raw==null?"":raw.toUpperCase(Locale.US).replaceAll("[^A-Z0-9]","").replace("USDT","");}
    private List<String> watchMatches(String raw){
        String q=watchQuery(raw);List<String> rows=new ArrayList<>();if(q.isEmpty())return rows;
        List<String> keys=new ArrayList<>(cryptoPrices.keySet());keys.sort((a,b)->{String aa=a.replace("USDT",""),bb=b.replace("USDT","");boolean ap=aa.startsWith(q),bp=bb.startsWith(q);if(ap!=bp)return ap?-1:1;return aa.compareTo(bb);});
        for(String sym:keys){String base=sym.replace("USDT","");if((base.startsWith(q)||base.contains(q))&&!rows.contains(sym)){rows.add(sym);if(rows.size()>=8)break;}}
        return rows;
    }
    private void renderWatchSuggestions(String raw){
        if(watchSuggestions==null)return;watchSuggestions.removeAllViews();String q=watchQuery(raw);if(q.isEmpty())return;List<String> rows=watchMatches(q);
        if(rows.isEmpty()){TextView none=tv("Không thấy trong feed hiện tại • vẫn có thể bấm Tìm / thêm để backend kiểm tra mã này",9,YELLOW,false);none.setPadding(dp(4),dp(5),dp(4),dp(5));watchSuggestions.addView(none);return;}
        for(String sym:rows){JSONObject live=cryptoPrices.get(sym);double px=live==null?0:live.optDouble("lastPrice",0);Button b=button(sym.replace("USDT","")+"   "+fmt(px),false,v->{if(watchSearchInput!=null)watchSearchInput.setText(sym.replace("USDT",""));commitWatchSearch();});LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(42));lp.setMargins(0,dp(3),0,dp(3));watchSuggestions.addView(b,lp);}
    }
    private void commitWatchSearch(){
        if(watchSearchInput==null)return;String raw=watchSearchInput.getText().toString();String symbol=normalizeWatch(raw);if(symbol.isEmpty()){showWatchKeyboard(watchSearchInput);Toast.makeText(this,"Nhập mã coin, ví dụ BTC hoặc XRP",Toast.LENGTH_SHORT).show();return;}
        watchSearchInput.setText("");hideWatchKeyboard();addWatch(symbol);
    }

'''
if needle not in s: raise SystemExit('watchPrefs needle missing')
s=s.replace(needle,helpers+needle,1)

# Replace Watchlist renderer with a focus-safe, explicitly keyboard-enabled search box and live suggestions.
start=s.index('    private void renderWatchlist(boolean animate){')
end=s.index('    private void loadAllPerformance()',start)
new=r'''    private void renderWatchlist(boolean animate){Runnable body=()->{
        content.removeAllViews();subtitle.setText("WATCHLIST • TÌM & PHÂN TÍCH COIN");content.addView(tv("Theo dõi coin",20,TEXT,true));content.addView(tv("Tìm coin theo mã • không chiếm 4 slot tín hiệu chính",9,MUTED,false));

        LinearLayout searchCard=card();searchCard.addView(tv("TÌM COIN",10,CYAN,true));searchCard.addView(tv("Gõ BTC, ETH, XRP, ZEC… rồi chọn gợi ý hoặc bấm Tìm / thêm",9,MUTED,false));
        LinearLayout add=row();EditText input=new EditText(this);watchSearchInput=input;input.setHint("Nhập mã coin…");input.setHintTextColor(MUTED);input.setTextColor(TEXT);input.setTextSize(14);input.setSingleLine(true);input.setFocusable(true);input.setFocusableInTouchMode(true);input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);input.setImeOptions(EditorInfo.IME_ACTION_SEARCH);input.setPadding(dp(14),0,dp(14),0);input.setBackground(shape(PANEL2,14,CYAN));input.setContentDescription("Ô tìm kiếm coin Watchlist");
        input.setOnClickListener(v->showWatchKeyboard(input));input.setOnFocusChangeListener((v,has)->{if(has)showWatchKeyboard(input);});input.setOnEditorActionListener((v,action,event)->{if(action==EditorInfo.IME_ACTION_SEARCH||action==EditorInfo.IME_ACTION_DONE){commitWatchSearch();return true;}return false;});
        input.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence x,int a,int b,int c){}public void onTextChanged(CharSequence x,int a,int b,int c){renderWatchSuggestions(String.valueOf(x));}public void afterTextChanged(Editable e){}});
        Button addBtn=button("Tìm / thêm",true,v->{if(input.getText().toString().trim().isEmpty())showWatchKeyboard(input);else commitWatchSearch();});
        LinearLayout.LayoutParams ip=new LinearLayout.LayoutParams(0,dp(50),1f);ip.setMargins(0,dp(10),dp(5),dp(4));add.addView(input,ip);LinearLayout.LayoutParams ab=new LinearLayout.LayoutParams(dp(104),dp(50));ab.setMargins(dp(5),dp(10),0,dp(4));add.addView(addBtn,ab);searchCard.addView(add);
        watchSuggestions=column();searchCard.addView(watchSuggestions);content.addView(searchCard);

        List<String> symbols=watchSymbols();if(symbols.isEmpty()){LinearLayout z=card();z.addView(tv("Chưa có coin nào trong Watchlist.",11,TEXT,true));z.addView(tv("Chạm ô Tìm coin để mở bàn phím và thêm mã muốn phân tích.",9,MUTED,false));content.addView(z);return;}
        content.addView(sectionHeader("WATCHLIST CỦA BẠN",symbols.size()+" coin • SCALP + SWING phân tích riêng",CYAN));
        for(String sym:symbols){JSONObject root=watchCache.get(sym),ticker=root==null?null:root.optJSONObject("ticker"),live=cryptoPrices.get(sym);double px=live!=null?live.optDouble("lastPrice",0):(ticker==null?0:ticker.optDouble("lastPrice",0));LinearLayout c=card();LinearLayout h=row();LinearLayout n=column();n.addView(tv(sym.replace("USDT"," / USDT"),16,TEXT,true));String provider=live!=null?cryptoProvider:(ticker==null?"—":ticker.optString("provider","—"));n.addView(tv(provider+" • "+cryptoState,8,stateColor(cryptoState),false));h.addView(n,new LinearLayout.LayoutParams(0,-2,1f));TextView price=tv(fmt(px),15,CYAN,true);h.addView(price);Button rm=button("×",false,v->removeWatch(sym));LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(dp(40),dp(36));rp.setMargins(dp(8),0,0,0);h.addView(rm,rp);c.addView(h);JSONObject styles=root==null?null:root.optJSONObject("styles");c.addView(watchStyleBlock("SCALP  •  5m / 15m / 1h",styles==null?null:styles.optJSONObject("SCALP")));c.addView(watchStyleBlock("SWING  •  1h / 4h / 1D",styles==null?null:styles.optJSONObject("SWING")));Button refresh=button(Boolean.TRUE.equals(watchLoading.get(sym))?"Đang phân tích…":"Phân tích lại",false,v->refreshWatchSymbol(sym,true));LinearLayout.LayoutParams fp=new LinearLayout.LayoutParams(-1,dp(42));fp.setMargins(0,dp(7),0,0);c.addView(refresh,fp);content.addView(c);}
    };if(animate)swap(body);else body.run();}

'''
s=s[:start]+new+s[end:]

# Keep the input stable if add/remove refreshes occur around typing; commit intentionally clears focus before add.
# Manifest resize is explicit for OEM keyboards (including Xiaomi/HyperOS).
m=m.replace('android:name=".MainActivity"\n            android:exported="true"', 'android:name=".MainActivity"\n            android:exported="true"\n            android:windowSoftInputMode="adjustResize"')

P.write_text(s)
G.write_text(g)
M.write_text(m)
print('patched SignalHub V3.18 Watchlist search fix')
