// Seed data for 高中语文知识学习在线评价系统
// In-memory mock database. Reset on server restart.

export interface KnowledgePoint {
  id: string;
  name: string;
  unitId: string;
  moduleId: string;
  mastery: number;      // 0-100
  frequency: number;   // 考频权重 1-10
  errorCount: number;
  prerequisites?: string[]; // 前置知识点 id
}

export interface Unit {
  id: string;
  name: string;
  moduleId: string;
  knowledgePoints: KnowledgePoint[];
}

export interface Module {
  id: string;
  name: string;
  units: Unit[];
}

export interface Question {
  id: string;
  moduleId: string;
  unitId: string;
  kpId: string;
  type: "choice" | "fill" | "short";
  difficulty: 1 | 2 | 3 | 4;
  material?: string;
  stem: string;
  options?: string[]; // for choice
  answer: string;
  analysis: string;
  errorType?: "记忆型" | "理解型" | "方法型" | "审题型";
}

export const modules: Module[] = [
  {
    id: "m1", name: "文言文基础",
    units: [
      {
        id: "u1", moduleId: "m1", name: "文言虚词",
        knowledgePoints: [
          { id: "k1", name: "虚词「以」的用法", unitId: "u1", moduleId: "m1", mastery: 42, frequency: 9, errorCount: 6 },
          { id: "k2", name: "虚词「而」的用法", unitId: "u1", moduleId: "m1", mastery: 55, frequency: 8, errorCount: 4 },
          { id: "k3", name: "虚词「之」的用法", unitId: "u1", moduleId: "m1", mastery: 68, frequency: 8, errorCount: 3 },
        ],
      },
      {
        id: "u2", moduleId: "m1", name: "文言实词",
        knowledgePoints: [
          { id: "k4", name: "实词一词多义", unitId: "u2", moduleId: "m1", mastery: 71, frequency: 7, errorCount: 3 },
          { id: "k5", name: "古今异义", unitId: "u2", moduleId: "m1", mastery: 64, frequency: 6, errorCount: 4 },
        ],
      },
      {
        id: "u3", moduleId: "m1", name: "文言句式",
        knowledgePoints: [
          { id: "k6", name: "判断句与被动句", unitId: "u3", moduleId: "m1", mastery: 58, frequency: 6, errorCount: 5 },
          { id: "k7", name: "宾语前置句", unitId: "u3", moduleId: "m1", mastery: 49, frequency: 7, errorCount: 6 },
        ],
      },
      {
        id: "u4", moduleId: "m1", name: "文言文翻译",
        knowledgePoints: [
          { id: "k8", name: "翻译六字法（留删换调补变）", unitId: "u4", moduleId: "m1", mastery: 73, frequency: 7, errorCount: 2 },
        ],
      },
    ],
  },
  {
    id: "m2", name: "古代诗歌鉴赏",
    units: [
      {
        id: "u5", moduleId: "m2", name: "诗歌意象",
        knowledgePoints: [
          { id: "k9", name: "常见意象与意蕴", unitId: "u5", moduleId: "m2", mastery: 51, frequency: 8, errorCount: 5 },
          { id: "k10", name: "意境画面概括", unitId: "u5", moduleId: "m2", mastery: 60, frequency: 6, errorCount: 3 },
        ],
      },
      {
        id: "u6", moduleId: "m2", name: "表现手法",
        knowledgePoints: [
          { id: "k11", name: "借景抒情与托物言志", unitId: "u6", moduleId: "m2", mastery: 63, frequency: 8, errorCount: 4 },
          { id: "k12", name: "用典与对比", unitId: "u6", moduleId: "m2", mastery: 47, frequency: 7, errorCount: 5 },
        ],
      },
      {
        id: "u7", moduleId: "m2", name: "思想情感",
        knowledgePoints: [
          { id: "k13", name: "情感主旨把握", unitId: "u7", moduleId: "m2", mastery: 56, frequency: 9, errorCount: 4 },
        ],
      },
      {
        id: "u8", moduleId: "m2", name: "炼字炼句",
        knowledgePoints: [
          { id: "k14", name: "炼字赏析", unitId: "u8", moduleId: "m2", mastery: 44, frequency: 7, errorCount: 6 },
        ],
      },
    ],
  },
  {
    id: "m3", name: "现代文阅读",
    units: [
      {
        id: "u9", moduleId: "m3", name: "论述类文本",
        knowledgePoints: [
          { id: "k15", name: "论点与论据关系", unitId: "u9", moduleId: "m3", mastery: 76, frequency: 8, errorCount: 2 },
          { id: "k16", name: "论证方法辨析", unitId: "u9", moduleId: "m3", mastery: 69, frequency: 7, errorCount: 3 },
        ],
      },
      {
        id: "u10", moduleId: "m3", name: "文学类文本",
        knowledgePoints: [
          { id: "k17", name: "人物形象分析", unitId: "u10", moduleId: "m3", mastery: 65, frequency: 8, errorCount: 3 },
          { id: "k18", name: "情节与环境作用", unitId: "u10", moduleId: "m3", mastery: 70, frequency: 7, errorCount: 2 },
        ],
      },
      {
        id: "u11", moduleId: "m3", name: "实用类文本",
        knowledgePoints: [
          { id: "k19", name: "信息筛选与概括", unitId: "u11", moduleId: "m3", mastery: 78, frequency: 6, errorCount: 2 },
        ],
      },
    ],
  },
  {
    id: "m4", name: "语言文字运用",
    units: [
      {
        id: "u12", moduleId: "m4", name: "成语运用",
        knowledgePoints: [
          { id: "k20", name: "易混成语辨析", unitId: "u12", moduleId: "m4", mastery: 62, frequency: 7, errorCount: 4 },
          { id: "k21", name: "成语对象误用", unitId: "u12", moduleId: "m4", mastery: 58, frequency: 6, errorCount: 3 },
        ],
      },
      {
        id: "u13", moduleId: "m4", name: "病句辨析",
        knowledgePoints: [
          { id: "k22", name: "语序不当与搭配不当", unitId: "u13", moduleId: "m4", mastery: 66, frequency: 8, errorCount: 3 },
          { id: "k23", name: "成分残缺与赘余", unitId: "u13", moduleId: "m4", mastery: 71, frequency: 7, errorCount: 2 },
        ],
      },
      {
        id: "u14", moduleId: "m4", name: "修辞手法",
        knowledgePoints: [
          { id: "k24", name: "比喻与比拟辨析", unitId: "u14", moduleId: "m4", mastery: 74, frequency: 6, errorCount: 2 },
        ],
      },
      {
        id: "u15", moduleId: "m4", name: "语言连贯",
        knowledgePoints: [
          { id: "k25", name: "语句衔接与排序", unitId: "u15", moduleId: "m4", mastery: 67, frequency: 7, errorCount: 3 },
        ],
      },
    ],
  },
  {
    id: "m5", name: "写作",
    units: [
      {
        id: "u16", moduleId: "m5", name: "议论文写作",
        knowledgePoints: [
          { id: "k26", name: "论点提炼与分论点", unitId: "u16", moduleId: "m5", mastery: 59, frequency: 9, errorCount: 4 },
          { id: "k27", name: "论证结构搭建", unitId: "u16", moduleId: "m5", mastery: 52, frequency: 8, errorCount: 5 },
        ],
      },
      {
        id: "u17", moduleId: "m5", name: "记叙文写作",
        knowledgePoints: [
          { id: "k28", name: "细节描写与情感", unitId: "u17", moduleId: "m5", mastery: 61, frequency: 7, errorCount: 3 },
        ],
      },
      {
        id: "u18", moduleId: "m5", name: "素材积累",
        knowledgePoints: [
          { id: "k29", name: "经典素材运用", unitId: "u18", moduleId: "m5", mastery: 57, frequency: 8, errorCount: 4 },
        ],
      },
    ],
  },
];

export const profile = {
  id: "u_1001",
  name: "李同学",
  grade: "高二",
  avatar: "",
  level: 3,
  beatPercent: 64,
  studyHours: 128.5,
  assessmentCount: 14,
  radar: [
    { dimension: "文言基础", value: 58 },
    { dimension: "诗歌鉴赏", value: 52 },
    { dimension: "现代文阅读", value: 71 },
    { dimension: "语言运用", value: 66 },
  ],
  gradeRadar: [
    { dimension: "文言基础", value: 65 },
    { dimension: "诗歌鉴赏", value: 60 },
    { dimension: "现代文阅读", value: 68 },
    { dimension: "语言运用", value: 70 },
  ],
};

export const todayTask = {
  id: "t_today",
  title: "文言虚词基础巩固",
  questionCount: 10,
  estMinutes: 15,
  progress: 30,
  kpId: "k1",
  type: "专项训练",
};

export const todos = {
  pendingAssessment: 2,
  pendingRetest: 1,
  pendingCorrection: 5,
};

export const bits = {
  title: "每日一识",
  content: "「以」作介词表工具，译为「拿、用」；作连词表目的，译为「来、以便」。",
  kpId: "k1",
};

export const assessments = [
  {
    id: "a1",
    type: "入门诊断",
    title: "入门综合诊断",
    desc: "全面检测五大模块知识掌握情况，定位整体短板。",
    duration: "约20分钟",
    count: 35,
    tag: "推荐首次使用",
    action: "开始测评",
  },
  {
    id: "a2",
    type: "单元专项",
    title: "单元专项诊断",
    desc: "针对单个知识单元精细化检测，定位具体知识点漏洞。",
    duration: "约8分钟",
    count: 15,
    tag: "适合专项突破",
    action: "选择单元",
  },
  {
    id: "a3",
    type: "阶段综合",
    title: "阶段综合测评",
    desc: "全模块综合检测，对标高考难度，检验阶段学习效果。",
    duration: "约45分钟",
    count: 35,
    tag: "月考/期中/期末适用",
    action: "选择阶段",
  },
];

export const stages = [
  { id: "s1", name: "月考", desc: "本月阶段性检测" },
  { id: "s2", name: "期中", desc: "期中考试难度" },
  { id: "s3", name: "期末", desc: "期末考试难度" },
  { id: "s4", name: "高考模拟", desc: "高考全真难度" },
];

export const assessmentHistory = [
  { id: "h1", name: "入门综合诊断", date: "2026-08-28", score: 78, level: 3, reportId: "r1" },
  { id: "h2", name: "文言文单元专项", date: "2026-08-24", score: 72, level: 3, reportId: "r2" },
  { id: "h3", name: "阶段综合测评(月考)", date: "2026-08-20", score: 81, level: 4, reportId: "r3" },
  { id: "h4", name: "诗歌鉴赏单元专项", date: "2026-08-15", score: 65, level: 2, reportId: "r4" },
];

export const questions: Question[] = [
  // k1 文言虚词「以」
  {
    id: "q1", moduleId: "m1", unitId: "u1", kpId: "k1", type: "choice", difficulty: 2,
    material: "阅读下面的文言文，回答问题。\n【材料】“以五十步笑百步，则何如？”（《孟子·梁惠王上》）",
    stem: "下列句中「以」的用法，与例句相同的一项是（例句：以五十步笑百步）",
    options: ["A. 予以贯之（拿、用）", "B. 以此知其必败（凭借）", "C. 皆以美于徐公（认为）", "D. 请以战喻（用）"],
    answer: "D",
    analysis: "例句「以五十步」中「以」为介词，表凭借，译为「用」。D项「请以战喻」同为介词「用」。A项「拿、用」、B项「凭借」虽同为介词但语义侧重不同，本题核心考点为介词表凭借/工具用法的辨析。",
    errorType: "理解型",
  },
  {
    id: "q2", moduleId: "m1", unitId: "u1", kpId: "k1", type: "choice", difficulty: 3,
    stem: "下列各句中，加点「以」字表示目的（来、以便）的是",
    options: ["A. 作《师说》以贻之", "B. 以子之矛攻子之盾", "C. 皆以美于徐公", "D. 以待来年"],
    answer: "A",
    analysis: "A项「作《师说》以贻之」中「以」连接前后动作，表目的，译为「来」。D项「以待来年」亦含目的意味，但A为最典型用法。注意区分介词「用/凭借」与连词「来/以便」。",
    errorType: "理解型",
  },
  {
    id: "q3", moduleId: "m1", unitId: "u1", kpId: "k1", type: "fill", difficulty: 2,
    stem: "「以」在「以勇气闻于诸侯」中作___词，译为___。",
    answer: "介词；凭借",
    analysis: "「以勇气」即「凭勇气」，「以」为介词表凭借、依据。",
    errorType: "记忆型",
  },
  // k2 而
  {
    id: "q4", moduleId: "m1", unitId: "u1", kpId: "k2", type: "choice", difficulty: 2,
    stem: "下列句中「而」表转折关系的是",
    options: ["A. 敏而好学", "B. 学而不思则罔", "C. 顺风而呼", "D. 拔剑击之而毁之"],
    answer: "B",
    analysis: "B项「学而不思」中「而」表转折，译为「却」。A表并列，C表修饰，D表顺承。",
    errorType: "理解型",
  },
  // k9 诗歌意象
  {
    id: "q5", moduleId: "m2", unitId: "u5", kpId: "k9", type: "choice", difficulty: 2,
    material: "【材料】“月落乌啼霜满天，江枫渔火对愁眠。”（张继《枫桥夜泊》）",
    stem: "诗中「月落」「霜满天」营造的氛围是",
    options: ["A. 明丽欢快", "B. 悠闲宁静", "C. 凄清孤寂", "D. 雄浑壮阔"],
    answer: "C",
    analysis: "「月落」「霜满天」「愁眠」等意象共同营造凄清、孤寂、愁苦的氛围，C正确。意象叠加是把握诗歌情感的关键。",
    errorType: "理解型",
  },
  // k11 表现手法
  {
    id: "q6", moduleId: "m2", unitId: "u6", kpId: "k11", type: "choice", difficulty: 3,
    material: "【材料】“感时花溅泪，恨别鸟惊心。”（杜甫《春望》）",
    stem: "「感时花溅泪，恨别鸟惊心」使用的主要表现手法是",
    options: ["A. 借景抒情（以乐景写哀情）", "B. 直抒胸臆", "C. 用典", "D. 对偶（仅修辞）"],
    answer: "A",
    analysis: "诗人以花鸟本应悦目之物反衬感时恨别之哀，属「以乐景写哀情」的借景抒情，A正确。D只见表层修辞而忽视手法本质。",
    errorType: "方法型",
  },
  // k14 炼字
  {
    id: "q7", moduleId: "m2", unitId: "u8", kpId: "k14", type: "short", difficulty: 4,
    material: "【材料】“红杏枝头春意闹”（宋祁《玉楼春》）",
    stem: "简析「闹」字的妙处。",
    answer: "「闹」字化静为动，赋予春意以生机与动态，写出春意盎然、繁盛之态；以拟人手法使画面鲜活，视听通感，极具感染力。",
    analysis: "炼字题答题路径：释义→手法→意境→情感。要点：化静为动、拟人、通感、意境盎然。",
    errorType: "方法型",
  },
  // k15 论述类
  {
    id: "q8", moduleId: "m3", unitId: "u9", kpId: "k15", type: "choice", difficulty: 2,
    material: "【材料】“论证需以事实为据，论据须与论点有本质联系，方能服人。”",
    stem: "根据材料，下列说法正确的是",
    options: ["A. 论据越多越好", "B. 论据与论点有本质联系即可服人", "C. 论证无需事实", "D. 论点可脱离论据"],
    answer: "B",
    analysis: "材料强调论据须与论点有本质联系，B正确。A「越多越好」偏离本质联系；C、D与文意相悖。",
    errorType: "审题型",
  },
  // k17 人物形象
  {
    id: "q9", moduleId: "m3", unitId: "u10", kpId: "k17", type: "short", difficulty: 3,
    stem: "简述分析小说人物形象的一般答题角度。",
    answer: "①概括人物身份、地位；②抓言行、心理、细节描写；③结合情节与环境；④联系主旨与作者情感。",
    analysis: "人物形象题四步：身份定位—描写分析—情节环境—主旨情感。",
    errorType: "方法型",
  },
  // k20 成语
  {
    id: "q10", moduleId: "m4", unitId: "u12", kpId: "k20", type: "choice", difficulty: 2,
    stem: "下列各句中，成语使用正确的是",
    options: ["A. 他的成绩一落千丈，令人刮目相看", "B. 这道难题他迎刃而解", "C. 面对强敌，他无所不为", "D. 作品匠心独运，令人叹为观止"],
    answer: "D",
    analysis: "D「匠心独运」「叹为观止」使用正确。A「刮目相看」指用新眼光看待进步，与成绩下降矛盾；B「迎刃而解」需先有「容易解决」的前提语境；C「无所不为」贬义，指什么坏事都干，误用。",
    errorType: "记忆型",
  },
  // k22 病句
  {
    id: "q11", moduleId: "m4", unitId: "u13", kpId: "k22", type: "choice", difficulty: 3,
    stem: "下列句子没有语病的是",
    options: ["A. 通过这次活动，使我深受教育", "B. 他年纪不大，许多人却对他格外敬重", "C. 我们要养成爱学习、爱思考", "D. 能否刻苦学习是取得好成绩的关键"],
    answer: "B",
    analysis: "A缺主语（「通过…使」掩盖主语）；C缺宾语（养成…习惯）；D两面对一面。B无语病。",
    errorType: "方法型",
  },
  // k26 议论文
  {
    id: "q12", moduleId: "m5", unitId: "u16", kpId: "k26", type: "short", difficulty: 3,
    stem: "请以「专」为题，拟写一个中心论点与两个分论点。",
    answer: "中心论点：唯有专注，方能成就卓越。分论点：①专注能汇聚心力，屏蔽纷扰；②专注能深耕细作，铸就品质。",
    analysis: "论点应鲜明、可议；分论点宜从「为什么/怎么做」角度展开，避免并列雷同。",
    errorType: "方法型",
  },
  // 额外变式题池（用于同类变式题）
  {
    id: "q13", moduleId: "m1", unitId: "u1", kpId: "k1", type: "choice", difficulty: 2,
    stem: "「以」在「不以物喜，不以己悲」中的用法是",
    options: ["A. 介词「因为」", "B. 连词「来」", "C. 动词「认为」", "D. 名词「原因」"],
    answer: "A",
    analysis: "「不以物喜」即「不因为外物而高兴」，「以」表原因，译为「因为」。",
    errorType: "理解型",
  },
  {
    id: "q14", moduleId: "m1", unitId: "u1", kpId: "k1", type: "fill", difficulty: 1,
    stem: "「以」作连词表修饰关系时，相当于现代汉语的「___」。",
    answer: "地",
    analysis: "表修饰的「而/以」连接状语与中心语，相当于「地」。",
    errorType: "记忆型",
  },
  {
    id: "q15", moduleId: "m1", unitId: "u1", kpId: "k1", type: "choice", difficulty: 3,
    stem: "下列句中「以」用法不同于其他三项的是",
    options: ["A. 以子之矛", "B. 以待来年", "C. 以理服人", "D. 以力服人"],
    answer: "B",
    analysis: "A、C、D「以」均为介词（用/凭借），B为连词表目的（来），故B不同。",
    errorType: "理解型",
  },
];

export interface PlanStage {
  id: string;
  name: string;
  goal: string;
  knowledgePoints: string[];
  estDays: number;
  status: "done" | "current" | "todo";
}
export interface PlanTask {
  id: string;
  date: string;
  title: string;
  content: string;
  estMinutes: number;
  status: "today" | "done" | "todo";
  kpId: string;
}
export const plan = {
  id: "p1",
  name: "文言虚词专项提升方案",
  goal: "掌握度从 40% 提升至 80%",
  totalDays: 7,
  completionRate: 28,
  stages: [
    { id: "st1", name: "基础巩固", goal: "掌握「以、而、之」核心义项", knowledgePoints: ["k1", "k2", "k3"], estDays: 3, status: "current" } as PlanStage,
    { id: "st2", name: "能力提升", goal: "语境辨析与一词多义迁移", knowledgePoints: ["k1", "k2"], estDays: 2, status: "todo" } as PlanStage,
    { id: "st3", name: "综合应用", goal: "文言翻译与真题综合", knowledgePoints: ["k1", "k8"], estDays: 2, status: "todo" } as PlanStage,
  ],
  tasks: [
    { id: "pt1", date: "2026-09-01", title: "「以」核心义项梳理", content: "学习「以」介词/连词/名词三类用法并完成练习", estMinutes: 15, status: "today", kpId: "k1" },
    { id: "pt2", date: "2026-09-02", title: "「而」用法专项", content: "梳理并列/承接/转折/修饰四种关系", estMinutes: 12, status: "todo", kpId: "k2" },
    { id: "pt3", date: "2026-09-03", title: "「之」用法专项", content: "代词/助词/动词三类辨析", estMinutes: 12, status: "todo", kpId: "k3" },
    { id: "pt4", date: "2026-08-31", title: "文言虚词总览复习", content: "回顾五大高频虚词", estMinutes: 10, status: "done", kpId: "k1" },
  ] as PlanTask[],
};

export interface ErrorItem {
  id: string;
  kpId: string;
  moduleId: string;
  difficulty: number;
  errorType: "记忆型" | "理解型" | "方法型" | "审题型";
  stem: string;
  material?: string;
  options?: string[];
  myAnswer: string;
  correctAnswer: string;
  cause: string;
  date: string;
  rework?: boolean;
  collected?: boolean;
}
export const errors: ErrorItem[] = [
  {
    id: "e1", kpId: "k1", moduleId: "m1", difficulty: 3, errorType: "理解型",
    stem: "「作《师说》以贻之」中「以」的用法",
    options: ["A. 介词「用」", "B. 连词「来」", "C. 动词「认为」", "D. 名词「原因」"],
    myAnswer: "A", correctAnswer: "B",
    cause: "混淆介词「用」与连词表目的「来」。「作…以贻之」前后为动作与目的关系，「以」为连词，译为「来」。",
    date: "2026-08-28",
  },
  {
    id: "e2", kpId: "k9", moduleId: "m2", difficulty: 3, errorType: "方法型",
    material: "“感时花溅泪，恨别鸟惊心。”",
    stem: "「感时花溅泪」主要表现手法判断",
    myAnswer: "对偶（仅修辞）", correctAnswer: "借景抒情（以乐景写哀情）",
    cause: "只见表层修辞而忽视手法本质。应识别「以乐景写哀情」的反衬手法。",
    date: "2026-08-27",
  },
  {
    id: "e3", kpId: "k20", moduleId: "m4", difficulty: 2, errorType: "记忆型",
    stem: "「刮目相看」使用是否正确：他的成绩一落千丈，令人刮目相看。",
    myAnswer: "正确", correctAnswer: "错误",
    cause: "「刮目相看」指用新眼光看待对方的进步，与「成绩下降」语境矛盾。",
    date: "2026-08-26",
  },
  {
    id: "e4", kpId: "k7", moduleId: "m1", difficulty: 3, errorType: "理解型",
    stem: "「句读之不知，惑之不解」句式判断",
    myAnswer: "判断句", correctAnswer: "宾语前置句",
    cause: "未识别「之」字复指前置宾语的结构。「不知句读」「不解惑」倒装为「句读之不知」。",
    date: "2026-08-25",
  },
];

// 成长时间序列
function buildSeries(days: number, base: number, drift: number) {
  const arr: { date: string; score: number; mastery: number }[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const noise = Math.round((Math.sin(i) + 1) * 2);
    const score = Math.min(100, base + (days - i) * drift + noise);
    const mastery = Math.min(100, Math.round(score * 0.7 + 20 + noise));
    arr.push({
      date: `${d.getMonth() + 1}/${d.getDate()}`,
      score,
      mastery,
    });
  }
  return arr;
}
export const growth = {
  week: buildSeries(7, 70, 0.6),
  month: buildSeries(30, 66, 0.4),
  semester: buildSeries(120, 58, 0.25),
  stats: {
    assessmentCount: 14,
    studyHours: 128.5,
    masteredPoints: 18,
    improvedModules: 2,
  },
  goal: {
    content: "学期末总分达到 85 分，文言基础模块掌握度 ≥ 80%",
    progress: 42,
    targetScore: 85,
    targetMastery: 80,
  },
};

// 报告生成（基于模块掌握度）
export function buildReport(reportId: string, sourceScore?: number) {
  const moduleStats = modules.map((m) => {
    const all = m.units.flatMap((u) => u.knowledgePoints);
    const avg = Math.round(all.reduce((s, k) => s + k.mastery, 0) / all.length);
    return { id: m.id, name: m.name, scoreRate: avg };
  });
  const allKp = modules.flatMap((m) => m.units.flatMap((u) => u.knowledgePoints));
  const gaps = [...allKp]
    .sort((a, b) => a.mastery - b.mastery)
    .slice(0, 8)
    .map((k, i) => ({
      id: k.id,
      name: k.name,
      mastery: k.mastery,
      module: modules.find((m) => m.id === k.moduleId)!.name,
      priority: i < 3 ? "优先补漏" : "一般",
    }));
  const errorCauses = [
    { type: "记忆型", percent: 22, desc: "对虚词义项、成语含义记忆不牢，需加强基础识记与默写。" },
    { type: "理解型", percent: 38, desc: "对文言虚词的语境辨析能力不足，一词多义迁移薄弱，建议结合语境反复推断。" },
    { type: "方法型", percent: 26, desc: "答题方法欠缺规范，如炼字题缺「释义—手法—意境—情感」路径。" },
    { type: "审题型", percent: 14, desc: "审题偏差，混淆「手法」与「修辞」、「句式」与「翻译」等概念。" },
  ];
  const score = sourceScore ?? Math.round(allKp.reduce((s, k) => s + k.mastery, 0) / allKp.length);
  const level = score >= 85 ? 5 : score >= 75 ? 4 : score >= 60 ? 3 : 2;
  return {
    id: reportId,
    score,
    level,
    beatPercent: Math.min(95, Math.round(score * 0.9 + 10)),
    conclusion: "整体基础中等偏上，文言基础与诗歌鉴赏为明显短板，建议优先突破虚词与表现手法。",
    modules: moduleStats.sort((a, b) => b.scoreRate - a.scoreRate),
    gaps,
    errorCauses,
    planSummary: {
      cycle: "7天",
      goal: "短板模块掌握度提升至 80%",
      stages: [
        "阶段一 基础巩固：核心虚词义项与意象梳理",
        "阶段二 能力提升：语境辨析与手法迁移",
        "阶段三 综合应用：真题翻译与鉴赏综合",
      ],
    },
  };
}

// 知识点学习内容
export const studyContent: Record<string, {
  lecture: string[];
  examples: { stem: string; answer: string; analysis: string; scoringPoints?: string[] }[];
  training: string[]; // question ids
}> = {
  k1: {
    lecture: [
      "「以」是文言高频虚词，主要有三类用法：介词、连词、名词（动词少见）。",
      "【介词】表凭借（用、凭借）、表工具（拿）、表原因（因为）、表时间（在）。如「以五十步笑百步」（凭借）、「以理服人」（用）、「不以物喜」（因为）。",
      "【连词】表目的（来、以便），如「作《师说》以贻之」；表修饰（地），如「木欣欣以向荣」。",
      "【易错点】混淆介词「用/凭借」与连词「来」：判断关键看前后是否为「动作—目的」关系。",
      "【方法】先判词性（介/连），再定语义，最后代入语境验证。",
    ],
    examples: [
      {
        stem: "辨析「以」在「皆以美于徐公」中的用法。",
        answer: "动词，译为「认为」。",
        analysis: "「皆以美于徐公」即「都认为（邹忌）美于徐公」，「以」后接宾语从句，为动词「认为」。",
        scoringPoints: ["判断词性", "准确释义", "代入语境"],
      },
    ],
    training: ["q1", "q13", "q2", "q14", "q15"],
  },
  k9: {
    lecture: [
      "意象是承载诗人主观情感的客观物象，如月（思乡）、柳（离别）、菊（高洁）。",
      "把握意象要关注其叠加营造的「画面感」与「氛围」，由景入情。",
      "「月落乌啼霜满天」叠用冷色调意象，营造凄清孤寂氛围。",
    ],
    examples: [
      { stem: "分析「江枫渔火对愁眠」的意象作用。", answer: "以江枫、渔火等暗淡意象衬托游子愁思，营造凄清孤寂之境。", analysis: "意象叠加→氛围→情感。" },
    ],
    training: ["q5"],
  },
  k11: {
    lecture: [
      "借景抒情：将情感寄寓景物描写中；托物言志：借客观物象寄托志向。",
      "「以乐景写哀情」为反衬手法，倍增其哀。",
      "区分手法与修辞：修辞是语言层面，手法是构思层面。",
    ],
    examples: [{ stem: "「感时花溅泪」手法辨析。", answer: "借景抒情（以乐景写哀情）。", analysis: "花鸟本乐，反衬感时之哀。" }],
    training: ["q6"],
  },
  k20: {
    lecture: [
      "辨析易混成语需把握：适用对象、感情色彩、语义轻重、语境是否匹配。",
      "「刮目相看」指看待他人的进步，对象须是人且须有进步。",
    ],
    examples: [{ stem: "判断「他的成绩一落千丈，令人刮目相看」是否正确。", answer: "错误。", analysis: "成绩下降与「进步」矛盾。" }],
    training: ["q10"],
  },
};

// 默认学习内容生成
export function getStudy(kpId: string) {
  if (studyContent[kpId]) return studyContent[kpId];
  const kp = allKp(kpId);
  if (!kp) return null;
  return {
    lecture: [
      `${kp.name}是${modules.find((m) => m.id === kp.moduleId)?.name}模块的重要知识点。`,
      "建议先掌握核心概念定义，再通过典型例题理解考查方式，最后用专项训练巩固。",
      `当前掌握度 ${kp.mastery}%，错题 ${kp.errorCount} 题，建议针对薄弱处加强。`,
    ],
    examples: questions.filter((q) => q.kpId === kpId).slice(0, 2).map((q) => ({
      stem: q.stem,
      answer: q.answer,
      analysis: q.analysis,
    })),
    training: questions.filter((q) => q.kpId === kpId).map((q) => q.id),
  };
}

export function allKp(kpId: string) {
  for (const m of modules) for (const u of m.units) for (const k of u.knowledgePoints) if (k.id === kpId) return k;
  return null;
}

// ============================================================
// 教师端数据
// ============================================================
export interface ClassStudent {
  id: string; name: string; score: number; level: number; mastery: number;
  trend: number; // 较上次 +/-
}
export interface ClassOverview {
  id: string; name: string;
  studentCount: number;
  avgScore: number;
  avgMastery: number;
  levelDist: { level: number; count: number }[];
  weakPoints: { kpId: string; name: string; module: string; errorRate: number; }[];
  students: ClassStudent[];
}
export const classes: ClassOverview[] = [
  {
    id: "c1", name: "高二(1)班", studentCount: 42, avgScore: 74, avgMastery: 68,
    levelDist: [{ level: 5, count: 3 }, { level: 4, count: 12 }, { level: 3, count: 18 }, { level: 2, count: 9 }],
    weakPoints: [
      { kpId: "k1", name: "虚词「以」的用法", module: "文言文基础", errorRate: 62 },
      { kpId: "k14", name: "炼字赏析", module: "古代诗歌鉴赏", errorRate: 58 },
      { kpId: "k7", name: "宾语前置句", module: "文言文基础", errorRate: 55 },
      { kpId: "k12", name: "用典与对比", module: "古代诗歌鉴赏", errorRate: 51 },
    ],
    students: [
      { id: "st1", name: "李同学", score: 78, level: 3, mastery: 64, trend: 4 },
      { id: "st2", name: "王同学", score: 86, level: 4, mastery: 79, trend: 6 },
      { id: "st3", name: "张同学", score: 65, level: 2, mastery: 52, trend: -3 },
      { id: "st4", name: "陈同学", score: 81, level: 4, mastery: 74, trend: 2 },
      { id: "st5", name: "刘同学", score: 72, level: 3, mastery: 66, trend: 1 },
      { id: "st6", name: "赵同学", score: 58, level: 2, mastery: 48, trend: -5 },
      { id: "st7", name: "孙同学", score: 90, level: 5, mastery: 88, trend: 3 },
      { id: "st8", name: "周同学", score: 69, level: 3, mastery: 60, trend: 0 },
    ],
  },
  {
    id: "c2", name: "高二(2)班", studentCount: 45, avgScore: 71, avgMastery: 65,
    levelDist: [{ level: 5, count: 2 }, { level: 4, count: 9 }, { level: 3, count: 20 }, { level: 2, count: 14 }],
    weakPoints: [
      { kpId: "k9", name: "常见意象与意蕴", module: "古代诗歌鉴赏", errorRate: 60 },
      { kpId: "k1", name: "虚词「以」的用法", module: "文言文基础", errorRate: 57 },
      { kpId: "k11", name: "借景抒情与托物言志", module: "古代诗歌鉴赏", errorRate: 49 },
      { kpId: "k22", name: "语序不当与搭配不当", module: "语言文字运用", errorRate: 46 },
    ],
    students: [
      { id: "st9", name: "吴同学", score: 83, level: 4, mastery: 76, trend: 5 },
      { id: "st10", name: "郑同学", score: 67, level: 3, mastery: 58, trend: -2 },
      { id: "st11", name: "钱同学", score: 75, level: 3, mastery: 70, trend: 3 },
      { id: "st12", name: "冯同学", score: 62, level: 2, mastery: 50, trend: -1 },
    ],
  },
];

export interface TeacherAssessment {
  id: string; name: string; type: string; className: string;
  status: "ongoing" | "done"; deadline: string;
  avgScore?: number; submission?: number; total?: number;
  gradeDist?: { range: string; count: number }[];
  correctRate?: { module: string; rate: number }[];
}
export const teacherAssessments: TeacherAssessment[] = [
  {
    id: "ta1", name: "月考综合测评", type: "阶段综合", className: "高二(1)班", status: "ongoing", deadline: "2026-09-03",
    submission: 38, total: 42,
  },
  {
    id: "ta2", name: "文言文单元专项", type: "单元专项", className: "高二(1)班", status: "ongoing", deadline: "2026-09-05",
    submission: 30, total: 42,
  },
  {
    id: "ta3", name: "入门综合诊断", type: "入门诊断", className: "高二(2)班", status: "done", deadline: "2026-08-28",
    avgScore: 72, submission: 45, total: 45,
    gradeDist: [
      { range: "90-100", count: 4 }, { range: "80-89", count: 11 }, { range: "70-79", count: 16 }, { range: "60-69", count: 9 }, { range: "0-59", count: 5 },
    ],
    correctRate: [
      { module: "文言文基础", rate: 62 }, { module: "古代诗歌鉴赏", rate: 55 }, { module: "现代文阅读", rate: 74 }, { module: "语言文字运用", rate: 70 }, { module: "写作", rate: 68 },
    ],
  },
  {
    id: "ta4", name: "阶段综合测评(月考)", type: "阶段综合", className: "高二(1)班", status: "done", deadline: "2026-08-20",
    avgScore: 76, submission: 42, total: 42,
    gradeDist: [
      { range: "90-100", count: 5 }, { range: "80-89", count: 13 }, { range: "70-79", count: 15 }, { range: "60-69", count: 7 }, { range: "0-59", count: 2 },
    ],
    correctRate: [
      { module: "文言文基础", rate: 65 }, { module: "古代诗歌鉴赏", rate: 58 }, { module: "现代文阅读", rate: 78 }, { module: "语言文字运用", rate: 72 }, { module: "写作", rate: 70 },
    ],
  },
];

// 学生个人学情（教师视角）—— 复用知识图谱/成长/错题，叠加教师备注
export interface StudentProfile {
  id: string; name: string; className: string; avgScore: number; level: number; rank: number;
  note: string;
}
export const students: StudentProfile[] = [
  { id: "st1", name: "李同学", className: "高二(1)班", avgScore: 78, level: 3, rank: 18, note: "文言虚词薄弱，建议优先突破「以」「而」专项。" },
  { id: "st2", name: "王同学", className: "高二(1)班", avgScore: 86, level: 4, rank: 6, note: "基础扎实，诗歌鉴赏炼字需强化。" },
  { id: "st3", name: "张同学", className: "高二(1)班", avgScore: 65, level: 2, rank: 35, note: "多项短板，需制定系统提升方案。" },
];

export function findStudent(id: string) {
  return students.find((s) => s.id === id) || null;
}

