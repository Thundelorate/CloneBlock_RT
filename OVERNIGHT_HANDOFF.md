# 9 月 11 日休息期间的工作交接

这批工作处理实验基础设施与证据可靠性。尚未下载真实数据、训练模型或产生论文实验结果，也没有租用服务器或产生云计算费用。

最终本地验证：`python -B -m unittest discover -s tests -v` 共 16 项测试通过；5 个涉及改动的 Python 入口通过语法检查；`bash -n scripts/setup_autodl.sh` 通过。完整测试使用现有 Python 3.10 / CPU PyTorch 环境。`artifacts/audit/local_preflight.json` 是本机环境诊断，不是实验结果，显示当前缺少多个音频依赖与电话编码器。

## 已完成的工作

| 文件 | 负责什么 | 当前验证范围 |
|---|---|---|
| `scripts/bootstrap_session_ci.py` | 为每个 K 的相似度、AUCK 和聚合增长量计算置信区间；比较防御与基线的配对差值 | 已知答案测试与命令行模拟数据测试；真实模型结果待运行 |
| `scripts/prepare_data.py` | 在裁剪录音时保存原始文件、原始句子编号、裁剪起止采样点和麦克风；独立固定说话人划分的随机种子 | 真实 WAV 裁剪逐采样测试；完整 VCTK 待下载 |
| `scripts/audit_experiment_data.py` | 检查训练、验证、测试集是否混入同一说话人，文件是否齐全，裁剪长度与记录是否一致 | 正常数据、重复数据和被修改的数据清单测试 |
| `scripts/setup_autodl.sh` | 在 Linux 服务器的独立 Python 环境安装候选依赖，并执行环境检查和测试 | Bash 语法已检查；没有在服务器执行安装 |
| `scripts/server_preflight.py` | 检查依赖能否导入、GPU 是否可用、简单梯度运算和电话编码器是否存在，保存实际依赖版本 | 本机运行正确报告依赖缺失；GPU 分支待服务器验证 |
| `requirements-server.txt` | 候选服务器环境中各 Python 软件包的版本清单 | 尚未证明整套依赖在目标服务器可安装、可推理；最终以服务器试跑为准 |

`scripts/run_session_pool_eval.py` 还增加了数据清单和配置文件的 SHA-256 校验值。统计工具读取这些信息，拒绝把不同数据、编码器或电话编码条件的实验混在一起比较。

## 这些统计术语是什么意思

- `K`：攻击者用于聚合的音频窗口数量，主实验固定为 1、2、4、8、16。
- `MeanSim@K`：选取 K 个窗口并合并其说话人表示后，与评估用参考表示的平均相似度。此处相似度越低，身份恢复越弱。
- `AUCK`：上述五个 K 点的相似度的等权平均。改变 K 的取值集合，也会改变这个指标。
- `CI`：confidence interval，置信区间。当前采用 95% 的 bootstrap 百分位区间。
- `bootstrap`：反复有放回抽样，用来估计当前测试样本带来的统计不确定性。这里每次抽取说话人，并保留该说话人的所有会话。
- `paired_delta`：同一批会话中，防御方法的指标减去基线指标。配对可以减少“抽到不同录音”造成的比较噪声。
- `slope_16_1`：相似度在 K=16 与 K=1 的差值，沿用原代码名称；它没有除以 K 的距离，并非通常意义上的导数。
- `SHA-256`：文件内容的校验值，用于确认两次实验是否使用相同文件；自行计算的校验值不等于已经核对过发布者的原始校验值。

这里的置信区间只描述固定模型、固定测试方案下的测试说话人抽样不确定性，不代表不同训练随机种子之间的波动。测试说话人很少时，区间本身也可能不稳定。EER、WER 和 XTTS 的区间尚未完成。

## 数据处理的明确变化

旧流程可能把两个麦克风的录音一起用于裁剪，也没有保存原始句子映射。新流程默认 `mic2`，与 [TorchAudio VCTK_092 的默认值](https://docs.pytorch.org/audio/2.5.0/generated/torchaudio.datasets.VCTK_092.html) 一致；可以通过 `--microphone mic1` 调整。每行数据同时保存实际麦克风标记，旧版无麦克风后缀的文件会标为 `unspecified`。

官方实现说明部分说话人的音频或文字缺失，因此不能把“语料标称说话人数”直接当成最终实验人数。我们将报告下载后实际可用、过滤后保留以及每个划分中的人数。官方来源同上。

新的 `source_path` 是相对原始数据目录的文件路径；`source_utter_id` 是原始句子编号；`source_start_sample` 和 `source_end_sample` 是重采样到 16 kHz 后的起止采样点，右端不包含在片段内；`is_full_utterance` 表示是否保留了整句。

保存了这些信息，仍不意味着裁剪片段可以用整句文字计算 WER。下一步需要从测试说话人的原始完整录音建立独立的质量评价清单，并修改 `run_quality_eval.py` 的输入与文字匹配。旧质量脚本仍不适合作为修订论文的最终 WER 入口。

重新准备的数据与旧论文的划分和裁剪结果可能不同。后续所有方法都必须在新固定的数据上重新评测；我们将如实报告这是重建后的实验协议。

## 醒来后的最短操作顺序

1. 开通 Linux GPU 实例，确认 GPU 型号、显存、数据盘容量和计费方式。告诉我可用的总预算上限，后续才能安排训练规模。
2. 在本机配置 SSH 连接。SSH 是远程连接服务器的工具；无需把密码或私钥发到聊天中。
3. 把本地当前项目传到服务器的数据盘，包括尚未提交 Git 的修改和新增文件。只从 GitHub 再克隆一次不会自动包含这些修改。
4. 在服务器项目根目录安装基础系统依赖，再运行环境准备脚本。以下命令会安装软件，但不会启动训练或下载语料：

```bash
apt-get update
apt-get install -y ffmpeg libsndfile1
# 当前 python 需为 3.10 或 3.11；如缺少 venv，安装对应 python 版本的 venv 包。
bash scripts/setup_autodl.sh
source .venv-main/bin/activate
```

候选方案使用匹配的 PyTorch/TorchAudio 2.5.1 和 CUDA 12.1 软件包，安装命令依据 [PyTorch 官方历史版本页](https://pytorch.org/get-started/previous-versions/)。这是为现有代码选定的试跑起点，不是旧实验的环境复原。XTTS 后续使用独立环境，避免语音合成依赖影响主实验。

5. 检查 `artifacts/env/server_preflight.json`。它只确认环境基础功能；数据和模型缺失会单独列出，不能将环境通过理解为全部实验就绪。
6. 由我接着安排下载 VCTK 0.92、确认目录和完整性，再运行新的准备和审计流程：

```bash
python scripts/download_vctk.py
python scripts/prepare_data.py --dataset vctk --microphone mic2 --seed 42
python scripts/audit_experiment_data.py
```

大规模预处理前先做小规模文件检查。下载脚本仍依赖上游地址在服务器上的可访问性，失败时需要检查网络与官方地址，不会把下载失败当成数据准备成功。

7. 先用少量会话测量推理耗时、显存和训练梯度，再估计完整实验需要多少 GPU 小时。不要直接运行旧的 `scripts/reproduce_paper.sh`，它仍包含旧检查点路径和待修订的 ASV/质量流程。

## 统计工具的运行方式

完整的基线和防御评价生成对应的 `session_attack_eval_*.json` 与 `session_attack_per_session_*.csv` 后，在同一目录保存两种文件，再运行：

```bash
python scripts/bootstrap_session_ci.py \
  --runs artifacts/tables/session_attack_eval_baseline_main.json \
         artifacts/tables/session_attack_eval_defense_main.json \
  --reference_method baseline --draws 2000 --seed 42 \
  --output artifacts/tables/main_ci.csv
```

上述文件名是运行方式示例，真实结果目前不存在。每个编码器、电话编码条件和攻击协议组合分别处理。统计工具要求所有方法具有完全一致的会话和 K 网格，遇到缺失会话会报错，需要查清原因后统一评价清单。

## 尚未解决的关键问题

| 问题 | 下一步 | 是否需要你现在处理 |
|---|---|---|
| 仓库没有原防御模型权重，也没有原始结果文件 | 检查可恢复来源；若无法恢复，明确安排从头训练并测量工期 | 你已说明现有资料全部给出，不需要重复寻找相同文件；醒来后可以联系原作者询问权重是否可取回 |
| 最强对比方法的实现和权重尚未核实 | 审计仓库与论文引用，确认可复现方案；不可用时调整比较范围并说明限制 | 暂不需要 |
| 当前 ASV 使用同会话参考 | 建立独立注册/测试录音和固定冒认者清单，再计算 EER 与分数差距 | 暂不需要 |
| 官方文字与裁剪片段不能直接对应 | 建立完整原句的质量清单，修正 WER 入口和跨方法信道共享 | 暂不需要 |
| realistic objective 训练仍待修改和验证 | 先检查梯度与训练目标，再进行 validation sweep 和短训练试跑 | GPU 接通后推进 |
| 论文只有 PDF | 根据 PDF 重建论文结构、公式和引用清单，使用会议模板；正文按作者提供的科学判断组织与修订 | 后续需要你与导师确认贡献、解释实验结果和最终稿 |

本轮完成的是可检查的代码和准备工具。Review matrix 中实验项仍保持开放，直到有真实数据证据或明确的限制说明。
