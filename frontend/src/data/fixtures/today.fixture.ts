import type { TodayContract } from '@/contracts'

/**
 * Sprint 4 Today Demo fixture。
 *
 * 内容逐字来自冻结原型 ui-prototypes/02-sakura-spring.html #view-today：
 * 文案、顺序、默认值（心情 calm / 时间 25 分钟）均不改动、不新增推荐。
 * 仅在 Demo Mode 使用；运行态不请求 API。
 */
export const todayFixture = {
  state: {
    status: 'ready',
    mode: 'demo',
  },
  dataAvailability: 'available',
  recommendationStatus: 'allowed',
  availability: {
    selectedTask: 'available',
    dailyTasks: 'available',
    sleepStats: 'available',
    visionStats: 'available',
    moodStats: 'available',
    rhythm: 'available',
    progress: 'available',
    replace: 'available',
    restore: 'available',
  },
  unavailableFields: [],
  heroTag: '✦ 春日极光 · 期中考试周 · 第 2 天',
  greetingLead: '早上好，',
  greetingName: '小满',
  summaryLines: [
    [
      { text: '昨晚睡了 ' },
      { text: '6 小时 50 分', emphasis: true },
      { text: '，比前天多 40 分钟——今天的状态，比昨天轻松一点。' },
    ],
    [
      { text: '微律准备了 ' },
      { text: '3 件微任务', emphasis: true },
      { text: '，都很小，小到像捡起一片花瓣。' },
    ],
  ],
  observation: {
    mainLead: '今天的状态，比昨天',
    mainEmphasis: '轻松一点',
    mainTail: '。',
    summary:
      '昨晚多睡了 40 分钟，今早的专注记录也更完整；连续用眼时间仍偏长——下午 16:20，微律在节奏里给你留了一朵「远眺」。',
    stats: [
      { key: '昨夜睡眠', value: '6 小时 50 分', delta: '↑ 比前天多 40 分', deltaTone: 'up' },
      { key: '连续用眼', value: '110 分钟', delta: '偏长 · 建议远眺', deltaTone: 'warn' },
      { key: '此刻情绪', value: '平静偏松', delta: '↗ 比昨天轻松', deltaTone: 'up' },
    ],
    suggestions: [
      {
        icon: 'flower',
        lead: '16:20 · 窗边远眺 20 秒',
        rest: '——两节自习之间，给眼睛放个小假。',
      },
      {
        icon: 'moon',
        night: true,
        lead: '21:40 · 花瓣呼吸',
        rest: '——睡前 2 分钟，把复习了一天的大脑轻轻放下。',
      },
    ],
  },
  moods: [
    { value: 'happy', face: '◕‿◕', label: '还不错' },
    { value: 'calm', face: '˘‿˘', label: '平静' },
    { value: 'tired', face: '>﹏<', label: '有点累' },
    { value: 'low', face: '·︿·', label: '有点低落' },
  ],
  defaultMood: 'calm',
  timeOptions: [
    { minutes: 10, label: '10 分钟' },
    { minutes: 25, label: '25 分钟' },
    { minutes: 40, label: '40 分钟以上' },
  ],
  defaultTimeMinutes: 25,
  moodNoteLead: '已计入：',
  moodNoteLines: ['下午体育课 40 分钟 · 明天数学考试', '怎么选都可以，微律只负责读懂你。'],
  tasksSectionTitle: '今日微任务',
  tasksSectionNote: '来自审核白名单 · 按你的画像生成',
  tasks: [
    {
      id: 'today-task-eye-look-far',
      tone: 'eye',
      domain: '用眼健康',
      meta: '约 1 分钟 · 极低强度',
      name: '窗边远眺 20 秒',
      description: '望向窗外最远的地方，数 20 秒。让眼睛在春天的远处，散一会儿步。',
      why: '上午你连续用眼 110 分钟没休息，远眺是负担最小的一朵「花瓣」。',
      whyIcon: 'flower',
    },
    {
      id: 'today-task-move-neck-stretch',
      tone: 'move',
      domain: '颈肩放松',
      meta: '约 3 分钟 · 低强度',
      name: '颈肩小伸展',
      description:
        '头缓缓向右倾，右手轻扶保持 15 秒，换边；再画圈转转肩膀 8 次。像春天伸懒腰的猫。',
      why: '你之前 6 次接受了课桌旁的拉伸，完成率 100%，是你最喜欢的任务类型。',
      whyIcon: 'flower',
    },
    {
      id: 'today-task-sleep-petal-breath',
      tone: 'sleep',
      domain: '睡前准备',
      meta: '约 2 分钟 · 极低强度',
      name: '花瓣呼吸 4-7-8',
      description: '吸气 4 秒，像捧起一片花瓣；屏息 7 秒，看它在掌心；呼气 8 秒，轻轻放它飞走。循环 4 次。',
      why: '昨晚只睡了 6 小时 10 分，明天还有考试。放慢呼吸，是给大脑最温柔的收尾。',
      whyIcon: 'flower',
    },
  ],
  /* 原型 REPLACE_POOL：模块级指针循环取用，静态、不请求推荐 API */
  replacePool: [
    {
      id: 'today-pool-move-walk',
      tone: 'move',
      domain: '轻活动',
      meta: '约 5 分钟 · 低强度',
      name: '走廊慢走 · 5 分钟',
      description: '离开座位，去走廊慢慢走上 5 分钟，让身体像春风里的柳条一样醒过来。',
      why: '替代任务同样来自审核白名单，强度略高一点，但考试周也适用。',
      whyIcon: 'flower',
    },
    {
      id: 'today-pool-eye-warm-palms',
      tone: 'eye',
      domain: '用眼健康',
      meta: '约 1 分钟 · 极低强度',
      name: '掌心热敷闭眼',
      description: '闭眼，双掌搓热，轻轻覆在眼睛上，休息 40 秒。黑暗里，眼睛会悄悄说谢谢。',
      why: '不用离开座位，自习间隙就能完成。',
      whyIcon: 'flower',
    },
    {
      id: 'today-pool-sleep-sunlight',
      tone: 'sleep',
      domain: '轻放松',
      meta: '约 3 分钟 · 极低强度',
      name: '窗边晒太阳 · 3 分钟',
      description: '站在窗边，让阳光落在脸上和后颈，什么都不想，就晒 3 分钟太阳。',
      why: '白天接触自然光，能帮今晚的你更快入睡。',
      whyIcon: 'flower',
    },
  ],
  /* 原型 moodRow low 分支：仅当 data-idx=1 的任务为 pending 时改写该卡 */
  lowMoodSwap: {
    taskId: 'today-task-move-neck-stretch',
    name: '闭眼听声音 · 1 分钟',
    description: '闭上眼睛，数一数能听到几种声音。风、翻书、远处的操场……只是听，什么都不用做。',
    why: '你选了「有点低落」，薇薇自动把活动类任务换成了更温柔的恢复类。',
  },
  rhythm: {
    title: '今天的节奏',
    sub: '按你的习惯轻轻排布',
    items: [
      { time: '17:30', title: '窗边远眺', note: '两节自习之间', now: true },
      { time: '18:10', title: '颈肩小伸展', note: '晚饭前 · 你偏好的时段' },
      { time: '21:40', title: '花瓣呼吸', note: '复习收尾后' },
    ],
  },
  breath: {
    title: '此刻 · 跟随呼吸',
    sub: '微律 AI 节律 · 9 秒一循环',
    tip: '这是微律的呼吸节律：吸气 20% · 呼气 80%。',
  },
  progressNotes: {
    hero: [
      '完成一件，就算今天有交代',
      '不错，慢慢来',
      '快收尾了，睡前那件最轻松',
      '今天有交代了 ✦',
    ],
    docked: [
      '捡起一片，就是今天的花瓣',
      '很好呀，慢慢来',
      '就剩一件啦',
      '今天的花瓣，凑齐啦 ✦',
    ],
  },
  feedbackCopy: {
    start: '⏱ 开始啦 · 不着急',
    done: '✦ 已记下这次完成 · 薇薇会记住的',
    partial: '🌱 部分完成也很棒 · 已记录',
    skip: '🕊 跳过也没关系 · 薇薇会降低这类任务的频率',
    restore: '',
    replace: '🌸 换好了 · 新任务同样来自审核白名单',
    lowMood: '🌷 收到 · 薇薇把任务都换成了最轻的',
    check: '✦ 从此刻的心情开始 · 30 秒完成今日检查',
  },
} satisfies TodayContract
