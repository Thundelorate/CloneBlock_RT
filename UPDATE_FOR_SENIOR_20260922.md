# CloneBlock-RT 补充实验与论文改版说明

**更新时间：** 2026-09-22
**用途：** 向项目原作者/学长同步本轮补充实验相对原 Interspeech 稿件与初始 GitHub 仓库的变化，并作为 ICASSP 新稿的事实依据。

## 1. 一句话总结

本轮工作没有更换 CloneBlock-RT 的核心流式 STFT 增益掩蔽结构，而是把原先偏理想化、证据链不完整的评测，升级为一个**面向真实攻击者可见信息、考虑多段语音聚合的会话级训练与评测框架**；同时补齐统计置信区间、跨编码器/跨编解码器、扰动预算、通话质量、实时性和小规模端到端 XTTS 验证，并纠正了原稿中不可复核的基线、WER 和 XTTS 结论。

## 2. 哪些属于技术调整，哪些属于实验补全

| 类型 | 本轮变化 | 性质与意义 |
| --- | --- | --- |
| 实质性方法/协议调整 | 引入 realistic self-consistency 攻击目标；以攻击者实际能截获的 `tele_defended` 语音构造选择目标；按会话聚合目标重新训练 | 不是单纯“补表格”，而是改变了攻击者信息边界和训练目标，是新稿最重要的技术增量 |
| 实质性方法/协议调整 | 将 clean-reference 目标重新定位为 information-privileged reference，而非 realistic 攻击 | 修复原稿威胁模型中“现实攻击”和“额外信息参考”混在一起的问题 |
| 必要实验补全 | validation sweep 选择扰动强度；bootstrap 95% CI；EER、target-impostor margin；扰动预算 | 属于可信论文应具备的模型选择、统计不确定性和安全/代价报告 |
| 必要实验补全 | Opus/G.711、ECAPA/x-vector、K=16/AUCK、CPU/GPU 流式延迟 | 检查结论是否依赖单一信道、单一说话人编码器或离线实现 |
| 探索性扩展 | 小规模 XTTS 端到端克隆实验 | 把“嵌入相似度下降”向实际克隆效果推进一步，但当前规模不足以宣称普适阻断 |
| 纠错与证据治理 | 重建 VCTK transcript 对齐的质量评测；撤下不可审计的 ClearMask/Enkidu 数字；替换旧 XTTS 结果 | 不属于算法创新，但对论文可信度至关重要，防止继续引用无法复现或定义错误的结果 |

## 3. 相对原论文的主要变化

### 3.1 威胁模型与协议

原稿以目标说话人的干净参考嵌入指导攻击选择，并将其作为主要 targeted setting。新协议把可见信息明确分成三层：

1. **Realistic / self-consistency（主结果）**：攻击者仅使用自己截获的防御后通话音频，在候选窗口之间计算一致性并选择/聚合，不需要额外干净注册语音。
2. **Information-privileged clean reference（参考结果）**：允许使用目标说话人的干净参考嵌入。它用于衡量额外身份信息带来的差异，但不再称为现实攻击或严格的理论 upper bound。
3. **Selection-source ablation（消融）**：比较用 `defended`（编解码前）和 `tele_defended`（经过电话信道后）嵌入进行窗口选择。主协议采用攻击者真正收到的 `tele_defended`。

其中：

- `clean`：原始干净语音；
- `defended`：经过 CloneBlock-RT 后、尚未经过电话编解码器的语音；
- `tele_clean`：干净语音经过电话信道后的版本；
- `tele_defended`：防御语音经过电话信道后的版本，也是现实攻击者可截获的信号。

### 3.2 训练目标与模型选择

原稿说明未使用 attacker-in-the-loop aggregation objective。本轮新增**session-level aggregation-aware objective**：训练时直接考虑同一会话中多个候选窗口如何被攻击者选择并聚合，使优化目标与最终的多窗口攻击协议一致。

扰动强度 `alpha` 不再只沿用固定值，而是在验证集上扫描 `0.12 / 0.18 / 0.24`。按 realistic self-consistency 的 K=16 和 AUCK 表现选择 `alpha=0.24`，随后完成 1000-step VCTK 正式重训练。该选择只使用 validation split，test split 仅用于最终报告。

验证集结果（越低代表攻击者聚合后的说话人相似度越低）：

| alpha | MeanSim@16 | AUCK |
| ---: | ---: | ---: |
| 0.12 | 0.9703 | 0.8831 |
| 0.18 | 0.9464 | 0.8619 |
| **0.24** | **0.9136** | **0.8333** |

### 3.3 数据与拆分

- 正式补充实验以 **VCTK 0.92** 为主；LibriSpeech dev-clean 仅用于辅助调试/先导实验。
- 构建了会话级池：train 255 sessions / 22,203 windows，validation 33 / 2,724，test 33 / 2,901。
- 最终测试包含 11 名说话人、33 个会话。
- 增加数据源、说话人/拆分和会话池审计，避免 train/validation/test 泄漏。
- 质量评测另建 200 条完整语音的确定性 manifest，使用 VCTK 官方 transcript，并为 clean/defended 使用同一信道随机条件做配对比较。

### 3.4 主安全结果

主表采用 **ECAPA** 说话人编码器、`tele_defended` 选择源、self-consistency realistic protocol。`MeanSim@K` 越低越好；K 表示攻击者从同一会话聚合的语音窗口数量。

| 系统 | MeanSim@1 | MeanSim@16 | AUCK |
| --- | ---: | ---: | ---: |
| No defense | 0.7322 | 0.9873 | 0.8889 |
| 原 reference-objective checkpoint | 0.6987 | 0.9444 | 0.8497 |
| **Realistic-objective retraining** | **0.6754** | **0.9130** | **0.8208** |

Realistic retraining 的 MeanSim@16 speaker-cluster bootstrap 95% CI 为 **[0.9013, 0.9235]**。这说明重训练后在现实的多窗口聚合攻击下优于旧 checkpoint，但结果仍不是“彻底阻断”：K 增大时攻击者仍能恢复较高相似度。

`AUCK` 定义为预设 K 曲线上的归一化均值/面积摘要，用来概括攻击者随聚合窗口数增加的整体表现；它不是额外独立的攻击成功率。

### 3.5 参考条件、信道与跨编码器检查

Clean-reference information-privileged setting 下，realistic retraining 的 MeanSim@16 / AUCK 为 **0.9083 / 0.8159**；该结果作为额外信息条件下的参考，不再写成已证明的 upper bound。

选择源消融：

| 编码器 | 选择源 | MeanSim@16 | AUCK |
| --- | --- | ---: | ---: |
| ECAPA | `tele_defended` | 0.9130 | 0.8208 |
| ECAPA | `defended` | 0.8986 | 0.7810 |
| x-vector | `tele_defended` | 0.9963 | 0.9884 |
| x-vector | `defended` | 0.9962 | 0.9865 |

电话编解码器检查（realistic retraining）：

| 条件 | MeanSim@16 | AUCK |
| --- | ---: | ---: |
| 无额外 codec | 0.9130 | 0.8208 |
| Opus 16 kb/s | 0.9096 | 0.8143 |
| G.711 | 0.9111 | 0.8206 |

这表明主趋势没有因 Opus/G.711 消失；但 x-vector 下的高相似度也说明防御效果明显依赖下游说话人表征，不能只凭 ECAPA 结果宣称跨模型普适有效。

### 3.6 ASV 指标和 target-impostor margin

新增标准自动说话人验证（ASV）指标：

- **EER (Equal Error Rate)**：误接受率与误拒绝率相等时的错误率；
- **target-impostor margin**：目标相似度与冒充者相似度之差，越小通常表示目标身份更难区分。

| 编码器 | 系统 | EER | target-impostor margin |
| --- | --- | ---: | ---: |
| ECAPA | No defense | 0.0000 | 0.2556 |
| ECAPA | Reference checkpoint | 0.0000 | 0.2449 |
| ECAPA | Realistic retraining | 0.0000 | 0.2380 |
| x-vector | No defense | 0.0818 | 0.008239 |
| x-vector | Reference checkpoint | 0.0909 | 0.007250 |
| x-vector | Realistic retraining | 0.0545 | 0.007223 |

该实验只有 22 个 target 和 220 个 impostor trials，应报告为小样本的 mixed result：margin 有下降趋势，但 EER 并未在两个编码器上形成一致改善。

### 3.7 扰动预算与通话质量

Realistic checkpoint 在 200 条样本上的防御扰动预算：

- RMS：0.00884；
- SNR：14.32 dB；
- relative L2：0.1925；
- L-infinity：0.0746；
- STOI(`tele_clean`, `tele_defended`)：0.9846。

其中 **STOI** 是短时客观可懂度指标；本稿明确比较经过相同电话链路的 `tele_clean` 与 `tele_defended`，而不是把 clean-vs-clean 的 1.0 当作防御质量结果。

原质量脚本的 crop 标识无法可靠对应官方 transcript，并曾退化为伪 ASR 参考，因此旧绝对 WER 结果作废。修正后使用 200 条 VCTK 完整语音与官方 transcript，报告配对的 **WER delta**：

| 信道 | WER delta | 95% CI | STOI |
| --- | ---: | --- | ---: |
| None | +0.00250 | [-0.00200, 0.00710] | 0.98436 |
| Opus | +0.00231 | [-0.00498, 0.01006] | 0.90676 |
| G.711 | +0.00468 | [-0.00315, 0.01231] | 0.97724 |

三个 WER delta 的置信区间均跨 0，未观察到稳定的额外识别退化。不过当前 ASR 后端在原始 clean 音频上的绝对 WER 约 1.0068，说明其绝对数值不可信，因此新稿只使用配对 delta，并把更强 ASR 后端验证列为限制。按照当前取舍，不新增 PESQ/DNSMOS。

### 3.8 小规模端到端 XTTS 实验

新增 20 sessions / 11 speakers、K=1 与 K=16、2 段文本、160 条合成语音的 XTTS 实验，共得到 320 个编码器评分。克隆语音使用独立 enrollment 做目标/冒充者比较，并采用 2000 次 speaker-cluster bootstrap。

关键结果：

- x-vector target-impostor margin delta：K=1 为 **-0.00246**，95% CI [-0.00504, -0.00019]；K=16 为 **-0.00296**，95% CI [-0.00521, -0.00052]。
- ECAPA 点估计同样下降，但 K=1 和 K=16 的 95% CI 均跨 0。
- 自然语音阈值对 baseline clone 和 defended clone 都几乎全部拒绝，因此 acceptance rate 在本设置下缺乏辨别力。
- K=64 参考音频超过 XTTS 默认 30 秒约束，故从本轮端到端实验中排除，而不再沿用旧稿中的 K=64 数字。

结论应写成：在小规模 XTTS 条件下，防御对 x-vector margin 出现稳定但幅度较小的下降，ECAPA 证据不确定；这支持“影响实际克隆表征”的可能性，但不能证明对不同 TTS/voice-cloning 系统普遍有效。

### 3.9 实时性与工程复现

- 20 ms chunk：CPU 0.560 ms，RTF 0.0280；GPU 0.745 ms，RTF 0.0373。
- 40 ms chunk：CPU 0.407 ms，GPU 0.747 ms。
- 两种设备均满足实时处理要求，且 20 ms CPU 结果足以支持实际通话端部署叙述。
- 增加服务器预检、数据审计、session pool 构建、bootstrap CI、训练/评测编排、产物导出和新服务器恢复脚本。
- 40/40 单元测试通过；fresh-clone 恢复检查中 36 个冻结证据/模型哈希全部通过。
- 当前可恢复快照：commit `d15632a5699222a7f28d280c78c14212b45255f3`，tag `icassp-snapshot-20260919`。

## 4. 原论文中需要替换或降调的内容

| 原论文/原结果 | 新稿处理 |
| --- | --- |
| 将 clean-reference targeted attack 写成现实主协议 | 改为 self-consistency realistic 主协议；clean reference 仅作 information-privileged reference |
| 方法部分声明没有 attacker-in-the-loop aggregation objective | 替换为本轮 session-level aggregation-aware objective 与重新训练结果 |
| 固定 `alpha=0.18` | 报告 validation sweep，并采用 `alpha=0.24` |
| ClearMask/Enkidu 数值对比 | 当前仓库无可审计实现、权重和完整 provenance；不再保留数字，只在 related work/limitations 中说明缺少 matched-budget baseline |
| 旧质量表及绝对 WER | 作废；替换为官方 transcript、完整语音、配对 WER delta 与 CI |
| 旧 XTTS 大幅下降及 K=64 结果 | 作废；替换为可审计的小规模 K=1/K=16 mixed result |
| “嵌入相似度下降直接等于阻止克隆” | 降调为 surrogate evidence，并用 XTTS 结果说明这种转化并不稳定 |
| 只报告点估计 | 关键结果增加 speaker-cluster paired bootstrap 95% CI |

## 5. 当前可以主张和不能主张的结论

### 可以主张

1. 在 VCTK 会话级评测中，按现实 self-consistency 聚合目标重训练，比旧 reference-objective checkpoint 更能降低 ECAPA 下的多窗口聚合相似度。
2. 主趋势在 Opus 16 kb/s 和 G.711 下保持，20 ms 流式推理满足实时要求。
3. 配对质量实验没有观察到稳定的额外 WER 增量，STOI 保持较高，但 Opus 本身显著降低 STOI。
4. 小规模 XTTS 实验中 x-vector margin 有统计可见但幅度较小的下降；ECAPA 结果不确定。

### 不能主张

1. 不能宣称对所有 speaker encoder、所有 voice-cloning/TTS 后端都有效。
2. 不能将 clean-reference 条件称为严格、已证明的 oracle upper bound。
3. 不能用当前 ASR 后端的绝对 WER 证明高识别质量。
4. 不能继续引用未审计的 ClearMask/Enkidu、旧 WER 或旧 XTTS/K=64 数字。
5. 不能把 bootstrap CI 当作多次训练种子的不确定性；当前正式模型只有一个训练 seed。

## 6. 新稿建议定位

建议标题：**CloneBlock-RT: Realistic Session-Level Defense Against Voice Cloning in Phone Calls**。

新稿不应包装成“完全不同的网络结构”，而应明确定位为：

> 我们识别并修复了流式语音克隆防御在多窗口会话攻击下的评测与训练错位问题，提出攻击者可观测、聚合感知的训练/评测协议，并给出跨信道、跨编码器、统计不确定性、质量、实时性和小规模端到端克隆证据。

这比简单追加实验更强，因为 realistic objective 会反过来改变 checkpoint 的训练方式；同时也比“全新架构”更克制，因为核心 STFT mask 网络保持不变。

## 7. 仍需学长确认或共同决定的事项

1. 新稿作者顺序、单位、通讯作者及每位作者贡献。
2. 是否能提供原始训练数据划分、checkpoint、ClearMask/Enkidu 运行记录或旧 XTTS 产物，以判断能否恢复严格的同预算外部基线。
3. 是否值得在投稿前追加多训练 seed；当前 CI 只覆盖测试说话人采样，不覆盖训练随机性。
4. 是否接受以“小规模 XTTS mixed result”如实入文，还是将其压缩为限制/附加实验。
5. 最终投稿年份、系统中的页数/匿名政策与 deadline，以官方当届 ICASSP paper kit 为准。

## 8. 缩写与变量速查

- **ASV**：Automatic Speaker Verification，自动说话人验证。
- **ECAPA / x-vector**：两类说话人嵌入模型，用于衡量身份相似度和跨模型迁移性。
- **K**：攻击者从同一会话中选取并聚合的语音窗口数。
- **MeanSim@K**：聚合 K 个窗口后与目标身份的平均余弦相似度；本实验中越低越好。
- **AUCK**：对预设 K 曲线进行归一化平均/面积汇总；越低越好。
- **EER**：Equal Error Rate，ASV 中误接受率与误拒绝率相等时的错误率。
- **WER**：Word Error Rate，词错误率。
- **STOI**：Short-Time Objective Intelligibility，短时客观可懂度。
- **RTF**：Real-Time Factor，处理时长除以音频时长；小于 1 表示可实时运行。
- **CI**：Confidence Interval，置信区间；本轮为 2000 次 speaker-cluster paired bootstrap 的 95% CI。
- **XTTS**：本轮使用的端到端文本到语音/声音克隆后端。
