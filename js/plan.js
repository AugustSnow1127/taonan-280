// Race plan data. All user-facing text in Traditional Chinese (Taiwan).
// Segment content is matched by the segment's midpoint km, so it keeps working
// if the reconstructed route or store list changes.

window.PLAN = {
  raceDate: '2026-10-31',
  sunset: '17:22',   // Tainan, 31 Oct (approx.)
  sunrise: '06:05',
  stopBudgetMin: 60,

  // Chinese display names for stop ids, used by the UI.
  stopNames: { start: '青埔起點', cp1: 'CP1 新竹風情海岸', s1: '7-11 通霄', r1: '大安休息站', s2: '7-11 梧棲', r2: '鹿港休息站（施工中）', cp2: 'CP2 王功福海宮', s3: '7-11 四湖', s4: '7-11 布袋', finish: '鹿耳門終點' },

  // Dwell minutes per stop id; fallback by type.
  // Rest areas are optional markers, not planned stops.
  dwellByType: { official: 10, store: 8, rest: 0 },
  dwellById: { start: 0, cp1: 5, finish: 0 },

  // Base speed (km/h) by km band. "Realistic fade" scenario.
  speedBands: [
    { from: 0,   to: 165, kmh: 20 },
    { from: 165, to: 205, kmh: 18 },
    { from: 205, to: 248, kmh: 17 },
    { from: 248, to: 999, kmh: 16 }
  ],

  // Strategy class by km band → line colour.
  strategyBands: [
    { from: 0,   to: 45,  cls: 'easy' },
    { from: 45,  to: 165, cls: 'steady' },
    { from: 165, to: 999, cls: 'critical' }
  ],

  segments: [
    {
      from: 0, to: 45,
      title: '市區出發：台31／台15',
      cadence: '85–90 rpm',
      effort: '自覺強度 3/10：還能唱歌',
      fuel: '0:30 吃 1 樣東西（香蕉或飯糰）。第 1 瓶裝運動飲料。',
      risk: '06:05 前天還沒亮：前後燈打開。沿途有紅綠燈、沒有封路，起點人多擁擠。',
      tactic: '不要追快的集團。CP1 關門只需要均速 12.8 km/h，這段是送分時間，不是比賽。',
      planB: '就算一路吃紅燈、均速掉到 18 km/h 以下也別管。即使只騎 15 km/h，到 CP1 仍有 1 小時以上緩衝。'
    },
    {
      from: 45, to: 110,
      title: '新竹海岸 → 台61 沿線',
      cadence: '85 rpm',
      effort: '自覺強度 4/10：能講完整句子',
      fuel: '每小時 60–75 g 碳水：每小時 1 包能量膠（25 g）＋ 500 ml 運動飲料（30 g）。每小時補水 500–750 ml。',
      risk: '海岸側風。台61 側車道路面與匯流口要小心。本地圖 km ~79–112 走台1 線（OSM 將台61 標為禁止自行車），當天請依大會指標行進。',
      tactic: '自己騎，用固定的踏頻和強度穩住 20 km/h，不要被超車的人帶快。',
      planB: '落後計畫 15 分鐘以上：水壺還有一半以上就跳過下一個超商補給點。'
    },
    {
      from: 110, to: 165,
      title: '台中 → 彰化（台17）：關門關鍵段',
      cadence: '85 rpm：提早換檔，維持轉動',
      effort: '自覺強度 4–5/10',
      fuel: '不餓也要每 45 分鐘吃一次。加一顆鹽錠或鹹的零食。',
      risk: '從這裡開始是你騎過最長的距離（個人最長紀錄 56 km 以上）。疲勞會悄悄找上門。',
      tactic: '目標 13:30 前抵達王功（CP2）＝ 60 分鐘緩衝。',
      planB: '預估 14:00 後才到 CP2 → 每站停留 ≤ 5 分鐘、邊騎邊吃，用停站時間把落後追回來。'
    },
    {
      from: 165, to: 205,
      title: '王功 → 雲林：午後高溫',
      cadence: '80–85 rpm',
      effort: '自覺強度 5/10：保護雙腿',
      fuel: '在 CP2 吃正餐（≤ 10 分鐘）。之後每小時 60 g 碳水。每瓶水都加電解質。',
      risk: '午後烈日加強風。過了一半距離後容易意志消沉。',
      tactic: '設定小目標：下一間超商，而不是台南。18 km/h 就夠了。',
      planB: '連續 30 分鐘低於 16 km/h → 立刻補 40 g 碳水（排除撞牆），再重新評估。'
    },
    {
      from: 205, to: 248,
      title: '雲林 → 嘉義：日落',
      cadence: '80 rpm',
      effort: '自覺強度 5–6/10',
      fuel: '有在用咖啡因的話，約 16:30 吃一包含咖啡因能量膠。在超商把兩瓶水都補滿。',
      risk: '日落約 17:22。天黑「之前」就在超商停靠時打開前後燈、穿上反光背心。',
      tactic: '入夜後跟其他車友一起騎。在台17 上成群騎比較安全也比較快。',
      planB: '預估 21:00 後才完賽 → 剩下的停靠點都縮成 3 分鐘補水。'
    },
    {
      from: 248, to: 999,
      title: '夜騎進台南',
      cadence: '80 rpm',
      effort: '自覺強度 6/10：最後 20 km 才把力氣用完',
      fuel: '每 40 分鐘一包能量膠。小口喝水，不要停車。',
      risk: '天色暗、疲勞、台南周邊車流多。每站停留不超過 5 分鐘。',
      tactic: '以 10 km 為單位倒數。前後燈都開，靠路邊穩定騎。',
      planB: '如果已經趕不上 21:00 關門，還是要安全騎完並安排接駁，安全第一。'
    }
  ],

  // Colours shared by map + legend.
  colors: {
    easy: '#2e9e5b', steady: '#d99a00', critical: '#d9452b', night: '#6a4fc4',
    stop: '#1f6feb',
    segmentPalette: ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#17becf', '#bcbd22']
  }
};

window.PREP = {
  calendar: [
    ['10/12（一）', '休息，或輕鬆踩 30 分鐘'],
    ['10/13（二）', '踏頻訓練 45 分鐘：5 × 3 分鐘 @ 95 rpm，間歇輕鬆踩 2 分鐘'],
    ['10/15（四）', '踏頻 60 分鐘：全程維持 85 rpm（換輕一點的檔）'],
    ['10/17（六）', '夜騎 60 分鐘：測試頭燈／尾燈、反光背心、電池續航'],
    ['10/20（二）', '踏頻訓練 45 分鐘：6 × 3 分鐘 @ 95 rpm'],
    ['10/22（四）', '踏頻 60 分鐘 @ 85 rpm ＋ 練習邊騎邊吃'],
    ['10/24（六）', '車輛檢查：煞車（必檢）、輪胎、鏈條。裝上號碼牌／晶片'],
    ['10/27（二）', '輕鬆踩 30 分鐘，加 3 × 1 分鐘 @ 100 rpm'],
    ['10/28（三）–10/30（五）', '減量期：休息。肝醣超補（見下方）'],
    ['10/31（六）', '比賽日：03:00 起床、04:00–04:50 報到、05:00 出發']
  ],
  cadence: [
    '你 10/10 那趟平均踏頻 62 rpm。280 km 的目標是 80–90 rpm。',
    '比直覺再輕一檔；速度靠轉速，不是靠硬踩。',
    '踏頻低＝每一踩出力更大＝雙腿更早沒力。這在 3 週內練得起來。'
  ],
  fuel: [
    '熱量需求 ≈ 23 kcal/km（你 56 km 那趟消耗 1,282 kcal）→ 280 km 約 6,400 kcal。',
    '不可能全部吃回來：目標每小時 60–75 g 碳水（約 240–300 kcal/h）。',
    '每小時補水 500–750 ml；每瓶水都加電解質。',
    '出發時隨身帶：6 包能量膠、2 條能量棒／飯糰、2 × 750 ml 水壺。其餘到超商補。'
  ],
  lastDays: [
    '週三至週五：每天每公斤體重 8–10 g 碳水（75 kg → 約 600–750 g）：白飯、麵、麵包。',
    '週五：低纖維，不嘗試新食物。19:00 前吃完晚餐，21:00 前上床。',
    '週四晚上的睡眠最關鍵，賽前一晚通常睡不多。',
    '比賽日早上 03:00：100–150 g 碳水（2 個飯糰＋香蕉＋運動飲料）。'
  ],
  gear: [
    '安全帽（前方貼號碼牌）',
    '計時晶片裝在座管',
    '前後煞車都正常（沒有煞車＝取消資格）',
    '頭燈：續航 ≥ 5 小時（05:00 摸黑出發＋17:20 到終點）',
    '尾燈：續航 ≥ 5 小時，另備一顆',
    '反光背心',
    '2 × 750 ml 水壺',
    '2 條備胎、挖胎棒、攜帶型打氣筒／CO₂',
    '行動電源＋線材（給車燈／手機／碼錶）',
    '碼錶（BSC200）已載入路線 GPX',
    '現金＋信用卡（超商用）',
    '屁屁膏、防曬乳',
    '夜騎段用的輕量外套',
    '行李吊牌掛在包包上（終點行李車用）',
    '身分證件＋手機鎖定畫面顯示緊急聯絡人'
  ]
};
