# 微律公开数据集资料目录

**更新日期：** 2026-08-11  
**状态：** 资料池，不是健康知识库，不是微律真实用户数据

## 使用边界

- 只可用于用户画像字段设计、群体变量分布理解、明确标注的合成用户、Personal RAG/协同过滤技术 POC 和论文背景分析。
- 不得写入 `health_knowledge_v1`、`micro_tasks_v1` 或 `user_memory_v1`。
- 不得把调查变量或统计结果当作个人健康事实、真实用户记忆、微任务依据或产品效果证明。
- 原始微观数据必须按官方条款取得和使用；不转存、不再分发、不尝试重新识别受访者。
- MovieLens 仅用于“协同过滤算法工程测试”。

## 总览

| dataset_id | 中文名 | 发布机构 | 人群/年龄 | 官方来源 | 注册/申请 | 当前获取状态 | 现在是否值得下载原始数据 |
|---|---|---|---|---|---|---|---|
| CEPS | 中国教育追踪调查 | 中国人民大学中国调查与数据中心 | 基线七/九年级；年龄不作固定限定 | [官方网站](https://ceps.ruc.edu.cn/) | 需在 CNSDA 注册并接受平台条款 | 问卷和数据使用手册已保存；微观数据未下载 | 暂不；先用问卷/手册完成画像字段设计 |
| YRBSS | 美国青少年风险行为监测系统 | U.S. CDC | 高中 9–12 年级，问卷选项覆盖约 12–18+ 岁 | [数据与文档](https://www.cdc.gov/yrbs/data/index.html) | 国家公用数据无需注册/付费 | 官方页、问卷和 codebook 已核验；PDF 直下返回 403 | 值得，但等进入画像分布实验时再下载 2023 ASCII 数据 |
| WHO_GSHS | 全球学校学生健康调查 | WHO，中国数据生产方为中国 CDC | 全球主要 13–17 岁；中国 2003 为 13–15 岁在校生 | [中国 2003 目录](https://extranet.who.int/ncdsmicrodata/index.php/catalog/17) | 不是学术申请制，但下载与使用须接受仓库条款 | 中文问卷和四地 codebook 已保存；微观数据未下载 | 暂不；先用数据字典完成变量映射 |
| PISA_2022 | PISA 2022 国际学生评估 | OECD | 15 岁在校学生 | [PISA 2022 Database](https://www.oecd.org/en/data/datasets/pisa-2022-database.html) | 公用文件无需注册 | 学生、well-being、ICT 问卷和 codebook 已保存；大型 PUF 未下载 | 暂不；PUF 较大，等明确变量和分析计划后再取 |
| CFPS | 中国家庭追踪调查 | 北京大学中国社会科学调查中心 | 家庭全年龄；含少儿问卷 | [公开数据申请指南](https://www.isss.pku.edu.cn/cfps/sjzx/gksj/) | 需注册、填写信息并等待审核（官方提示通常 3 个工作日） | 只登记官方入口和规则；未申请、未下载 | 暂不；第二优先级，且需先确认所需轮次 |
| NHANES_YOUTH | NHANES 儿童青少年子样本 | U.S. CDC/NCHS | 不同组件年龄范围不同，可筛选儿童/青少年 | [数据与文档](https://wwwn.cdc.gov/nchs/nhanes/default.aspx) | 公用文件无需注册；敏感变量可能限制访问 | 只登记官方入口；未下载 | 暂不；第二优先级且需按周期/组件精确选取 |
| NSCH | 美国儿童健康调查 | U.S. Census Bureau 代 HRSA MCHB 执行 | 0–17 岁；可单独取 12–17 岁问卷 | [2024 数据页](https://www.census.gov/programs-surveys/nsch/data/datasets.2024.html) | 公用文件无需注册 | 官方变量表已核验；微观数据未下载 | 暂不；第二优先级，先用互动 codebook 定位变量 |
| MOVIELENS_LATEST_SMALL | MovieLens Latest Small | GroupLens Research | 电影评分用户，不是青少年健康样本 | [官方数据页](https://grouplens.org/datasets/movielens/latest/) | 下载无需注册；使用/再分发必须遵守 README | 官方 README 已保存；1 MB ZIP 续传未完成，无效残片已删除 | 值得，但只在开始协同过滤工程测试时再下载 |

## CEPS

- **dataset_id:** `CEPS`
- **中文名/英文名：** 中国教育追踪调查 / China Education Panel Survey
- **调查年份：** 2013–2014 学年基线；2014–2015 起追访，后续轮次以官方平台为准。
- **样本规模：** 基线 19,487 名学生（10,279 名七年级、9,208 名九年级），来自 112 所学校、438 个班、28 个县级单位。
- **相关变量：** 学生基本信息、身心健康、学习状态、学习/活动时间、课外活动、家庭教育环境、师生/同伴关系、学校设施和管理。
- **获取方式/限制：** 问卷和手册公开；微观数据由 CNSDA/官方入口管理。不得尝试识别匿名的地区、学校或个人。
- **推荐用途：** 微律画像字段的中国初中场景依据，合成用户的联合分布参考。
- **不允许用途：** 不得冒充微律用户，不得作为健康事实、任务效果或学生个人评价。
- **codebook/questionnaire：** [调查问卷](https://ceps.ruc.edu.cn/xmwd/dcwj.htm) · [技术报告/数据手册](https://ceps.ruc.edu.cn/xmwd/jsbg.htm)

## YRBSS

- **dataset_id:** `YRBSS`
- **中文名/英文名：** 美国青少年风险行为监测系统 / Youth Risk Behavior Surveillance System
- **国家/年份：** 美国；国家 YRBS 主要为 1991–2023 隔年调查；2025 问卷已发布，本目录不将其当作已发布数据年。
- **2023 样本规模：** 20,103 份可用问卷（样本与响应率见 2023 Data User's Guide）。
- **相关变量：** 体育活动、运动团队、睡眠时长、非学习屏幕/电子设备使用、久坐替代指标、学校联结、心理状态和保护因素。
- **获取方式/许可：** CDC 公开 ASCII/Access 数据、程序和用户指南；官方 FAQ 说明无需费用和使用许可申请。
- **推荐用途：** 美国高中生行为变量设计和合成数据边际分布参考。
- **不允许用途：** 不可直接推断中国学生分布，不可当作微律效果样本。
- **codebook/questionnaire：** [2023 问卷](https://www.cdc.gov/yrbs/media/pdf/2023/2023_YRBS_National_HS_Questionnaire.pdf) · [2023 用户指南和 codebook](https://www.cdc.gov/yrbs/media/pdf/2023/2023_National_YRBS_Data_Users_Guide508.pdf)

## WHO GSHS

- **dataset_id:** `WHO_GSHS`
- **中文名/英文名：** 全球学校学生健康调查 / Global School-based Student Health Survey
- **人群/地区/年份：** 全球框架面向 13–17 岁在校生；中国当前官方目录中的历史数据为 2003 年北京、杭州、武汉、乌鲁木齐，宇宙为 13–15 岁在校生。
- **样本规模：** 北京 2,348，杭州 1,802，武汉 1,947，乌鲁木齐 2,918；合计 9,015 份公用记录。
- **相关变量：** 体育活动、上下学活动、久坐行为、饮食、心理健康、同伴/家长保护因素等；2003 中国问卷的“不能入睡”不等于睡眠时长。
- **获取方式/限制：** 微数据仍可从 WHO NCD Microdata Repository 公开获取，但仅限统计/科学研究、不得再分发或试图重新识别，发表时需按仓库要求引用。
- **推荐用途：** 跨国青少年健康行为字段对照；中国 2003 只作历史和四城市背景。
- **不允许用途：** 不可将 2003 四城数据宣称为当代中国全国分布。
- **codebook/questionnaire：** [官方相关资料](https://extranet.who.int/ncdsmicrodata/index.php/catalog/17/related_materials) · [数据字典](https://extranet.who.int/ncdsmicrodata/index.php/catalog/17/data-dictionary)

## PISA 2022

- **dataset_id:** `PISA_2022`
- **中文名/英文名：** 国际学生评估项目 2022 / Programme for International Student Assessment 2022
- **人群/地区/样本：** 15 岁在校生；81 个参与国家/经济体，约 69 万名学生，代表约 2,900 万名学生。
- **相关变量：** 学习环境、师生关系、学校氛围、well-being、ICT 使用与熟悉度、学习动机、社会经济背景。
- **获取方式/限制：** OECD 公开问卷、codebook、compendia 和 SAS/SPSS PUF；分析必须使用抽样权重、复制权重和 plausible values，不能把普通行级平均当作正式结论。
- **推荐用途：** 学习、well-being、ICT 和学校环境画像字段设计。
- **不允许用途：** 不可用于个人诊断、微任务生成或个人记忆。
- **codebook/questionnaire：** [PISA 2022 Database](https://www.oecd.org/en/data/datasets/pisa-2022-database.html)

## CFPS

- **dataset_id:** `CFPS`
- **中文名/英文名：** 中国家庭追踪调查 / China Family Panel Studies
- **人群/年份：** 全年龄家庭追踪，含少儿家长代答和 10 岁及以上个人自答模块；2010 年启动、隔年跟踪。官方公开新闻可核实至 CFPS2020 测试版；2022/2024 调查轮次存在，其公开数据发布状态需登录平台核实。
- **样本规模：** 本轮未从无需登录的官方页得到可稳定核对的最新轮次样本数，暂不填报。
- **相关变量：** 家庭结构、教育、作息、健康自评、心理状态、家庭关系、社区环境。
- **获取方式/限制：** 公用数据也需注册并等待审核；北大拥有数据版权，不得在未授权的第三方平台再分享原始或改造数据；受限地理变量要求更严。
- **推荐用途：** 中国家庭和社会环境字段的第二优先级补充。
- **不允许用途：** 不写入用户记忆，不用受限地理信息尝试重新识别家庭。
- **codebook/questionnaire：** [官方项目页](https://www.isss.pku.edu.cn/cfps/) · [公开数据申请](https://www.isss.pku.edu.cn/cfps/sjzx/gksj/)

## NHANES Youth

- **dataset_id:** `NHANES_YOUTH`
- **中文名/英文名：** 国家健康与营养调查儿童青少年子样本 / National Health and Nutrition Examination Survey Youth Subsample
- **人群/地区/年份：** 美国全国；各问卷、体检和实验室组件有不同年龄边界；Continuous NHANES 自 1999 年起按周期发布。
- **样本规模：** 不是单一青少年数据集，必须按周期、组件和年龄筛选；本目录不填一个误导性总样本数。
- **相关变量：** 体育活动、久坐/屏幕、睡眠、体格测量、饮食、社会经济信息；具体可用性需查每个周期的 codebook。
- **获取方式/限制：** 公用 XPT 和文档可直接下载；一些青少年敏感变量不在公用文件中，需通过 NCHS Research Data Center 申请。
- **推荐用途：** 美国青少年健康行为与客观测量字段的技术对照。
- **不允许用途：** 不得直接外推中国学生，不作为个人建议依据。
- **codebook/questionnaire：** [NHANES 数据与文档](https://wwwn.cdc.gov/nchs/nhanes/default.aspx) · [问卷数据列表](https://wwwn.cdc.gov/nchs/nhanes/Search/DataPage.aspx?Component=Questionnaire)

## NSCH

- **dataset_id:** `NSCH`
- **中文名/英文名：** 美国儿童健康调查 / National Survey of Children's Health
- **人群/地区/年份：** 美国 0–17 岁非机构居住儿童；2016 年起每年调查，官方当前数据页可见至 2024。
- **主版本：** 当前官方已发布的 2024 NSCH。
- **相关变量：** 12–17 岁问卷的体育活动、睡眠、屏幕时间、学校/课后经历、家庭交往、社区环境和情绪/发展状态。
- **获取方式/限制：** Census 公开 SAS/STATA PUF、变量表、频数表和用户指南；调查为家长/熟悉儿童的成年人回答，不应当作青少年自报。
- **推荐用途：** 家庭、学校、社区和健康行为联合字段的第二优先级补充。
- **不允许用途：** 不将家长报告与学生自报混为同一口径，不直接外推中国。
- **codebook/questionnaire：** [2024 数据页](https://www.census.gov/programs-surveys/nsch/data/datasets.2024.html) · [互动 codebook](https://www.census.gov/data-tools/demo/uccb/nschdict)

## MovieLens

- **dataset_id:** `MOVIELENS_LATEST_SMALL`
- **中文名/英文名：** MovieLens 最新小型数据集 / MovieLens Latest Small
- **人群/年份/样本：** 电影评分用户；官方页标注 2018-09 更新；约 600 用户、10 万评分和 3,600 标签应用。
- **获取方式/限制：** 官方 ZIP 公开下载；使用、引用和再分发以随包 README 为准，GroupLens 明确提醒通常不允许公开再分发。
- **唯一推荐用途：** “协同过滤算法工程测试”。
- **不允许用途：** 青少年健康数据、用户需求依据、Personal RAG 真实用户依据、微律效果证明。
- **README/data：** [官方页](https://grouplens.org/datasets/movielens/latest/) · [README](https://files.grouplens.org/datasets/movielens/ml-latest-small-README.html) · [ZIP](https://files.grouplens.org/datasets/movielens/ml-latest-small.zip)

## 本地存档

所有成功保存的官方问卷、codebook 和 README 位于 `archive/`，逐文件 URL、字节数和 SHA-256 见 [`downloads-manifest.jsonl`](downloads-manifest.jsonl)。本轮未保存 CEPS/CFPS/YRBSS/GSHS/PISA/NHANES/NSCH 的微观原始数据。
