/* Appended to extracted production functions by test_screensaver_wake.py. */
static void reset(int state){
 us=1000000; audio=repaints=0;deadline=0;
 memset(&pins,0,sizeof pins);
 lcd_command_state=lcd_data_state=lcd_clear_state=0;
 display_refresh_state=display_needs_refresh=display_needs_clear_all=0;
 refresh_i=refresh_j=visibleCursor=0;
 memset(currentDisplayBuffer,'A',sizeof currentDisplayBuffer);
 memset(editDisplayBuffer,'A',sizeof editDisplayBuffer);
 screensaver_Active=1;screensaver_cellState=state;screensaver_activeCell=23;
 screensaver_processTime=HAL_GetTick()+500;
}
static void check_woken(void){
 assert(!screensaver_Active && display_needs_clear_all && !repaints);
 assert(!lcd_command_state && !lcd_data_state && !lcd_clear_state);
 assert(screensaver_timer==0 && screensaver_Timeout==SCREENSAVER_SYSTICK);
}
int main(void){
 // All animation-only wait states, every remaining millisecond of the deadline.
 const int waits[]={CELL_NEW_POS,CELL_OFF_WAIT,CELL_1_WAIT,CELL_2_WAIT};
 for(unsigned i=0;i<sizeof waits/sizeof waits[0];i++){
  for(int remaining=0;remaining<=500;remaining++){
   reset(waits[i]); screensaver_timer=77;screensaver_Timeout=1;
   screensaver_processTime=HAL_GetTick()+remaining;
   uint64_t start=us;screensaver_touch();
   check_woken();
   assert(us-start<=1); // no animation wait, no LCD work at these boundaries
   assert(audio==0);
  }
 }
 // Reach each actual nonblocking phase, including clear's long hardware delay.
 const int states[]={CELL_OFF,CELL_1_SET_CURSOR,CELL_1_PRINT,
                     CELL_2_SET_CURSOR,CELL_2_PRINT,CELL_3_SET_CURSOR,CELL_3_PRINT};
 for(unsigned i=0;i<sizeof states/sizeof states[0];i++){
  for(int row=0;row<2;row++){
   int phases=states[i]==CELL_OFF?7:6;
   for(int phase=0;phase<phases;phase++){
    reset(states[i]);screensaver_activeCell=row?23:7;
    for(int j=0;j<phase;j++){
     assert(screensaver_process()==1);
     us+=200;
    }
    // A phase is entered through the real driver, not injected state values.
    if(states[i]==CELL_OFF){
     assert(phase==6 ? lcd_clear_state==1 : lcd_command_state==phase);
    }else if(states[i]==CELL_1_PRINT || states[i]==CELL_2_PRINT || states[i]==CELL_3_PRINT){
     assert(lcd_data_state==phase);
    }else assert(lcd_command_state==phase);
    uint64_t start=us;
    screensaver_touch();check_woken();
    assert(us>=start && us-start<11000);
    if(phase<5 || states[i]==CELL_OFF) assert(audio>0);
    if(us-start>1) assert(audio>0);
    assert(!(pins.ODR & LCD_E_Pin)); // both nibbles finished, enable low
    assert(screensaver_cellState==states[i]+1 ||
           (states[i]==CELL_3_PRINT && screensaver_cellState==CELL_NEW_POS));
   }
  }
 }
 // Inactive touches must only rearm the idle timer, not drain or repaint.
 reset(CELL_1_WAIT);screensaver_Active=0;
 for(int i=0;i<3;i++){
  screensaver_timer=99;screensaver_Timeout=2;
  uint64_t start=us;uint32_t due=screensaver_processTime;
  screensaver_touch();
  assert(us==start && screensaver_processTime==due && !audio && !repaints);
  assert(!display_needs_clear_all && screensaver_cellState==CELL_1_WAIT);
  assert(!screensaver_timer && screensaver_Timeout==SCREENSAVER_SYSTICK);
 }
 // Wake requests a deferred repaint, preserving cached/edit text until UI handoff.
 reset(CELL_OFF_WAIT);screensaver_touch();check_woken();
 for(int i=0;i<2;i++)for(int j=0;j<16;j++){
  assert(currentDisplayBuffer[i][j]=='A' && editDisplayBuffer[i][j]=='A');
 }
 // Busy menu sender defers invalidation until it is idle.
 display_refresh_state=2;menu_uiTick();assert(!repaints && display_needs_clear_all);
 display_refresh_state=0;menu_uiTick();
 assert(repaints==1 && !display_needs_clear_all && display_needs_refresh);
 for(int i=0;i<2;i++)for(int j=0;j<16;j++)assert(currentDisplayBuffer[i][j]==127);
 unsigned calls=0;
 do{assert(++calls<100000);}while(sendDisplayBuffer()!=0);
 assert(!memcmp(currentDisplayBuffer,editDisplayBuffer[0],16));
 assert(!memcmp(currentDisplayBuffer[1],editDisplayBuffer[1],16));
 menu_uiTick();assert(repaints==1);
 // Existing pending-menu flush still completes before the screensaver drain.
 reset(CELL_OFF_WAIT);display_needs_refresh=1;
 memset(currentDisplayBuffer,127,sizeof currentDisplayBuffer);
 screensaver_touch();check_woken();assert(!display_refresh_state);
 puts("PASS: wake deadlines, LCD phases/audio service, inactive touches, deferred redraw");
 return 0;
}
