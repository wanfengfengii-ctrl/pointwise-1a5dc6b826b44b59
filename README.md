# 槐巷剧场提词服务

槐巷社区小剧场的编排员从台本和走台记录登记提示卡，发行员将当晚的提示正文和使用优先级冻结为发行件。舞监为场次领取发行件，按直接键或提交人工请求发卡。左右侧幕按实际发出次序取阅，场务按实发证据签存。

## 运行

在项目根目录使用 Python 3.11，依赖均在标准库中。服务只监听本机 `127.0.0.1`，启动时输出实际端口。数据库路径可复用，重复启动保留草稿、发行、首执和结场件。

```sh
python3 -B -m control.http --database ./prompts.sqlite3 --port 8010
python3 -B check_project.py
python3 -B -m tests.demo
```

`check_project.py` 由运行平台在物化时提供。完整 unittest 也可用 `python3 -B -m unittest discover -s tests -t .` 执行。演示使用独立临时库，通过真实 HTTP 办理并保留该库重开一次。

## 当晚流程

1. 登记 `samples/show.json` 中的 D。换景组 G 的来序是 B、A，发行序是 A、B、C。
2. 提交含未知成员 X 的改稿会收到 422，D 保持上一份有效值。
3. 用 I1 签出 E1。改稿再签得到新版，按 E1 查回的卡文和卡序仍是最初内容。
4. 场 S 领取 E1，绑定 K 到 G、L 到 H，并指定 A、C 必发。
5. 按 K 从 G 发出 A，实发序为 1。此时尚欠 C，申请结场收到 409。
6. 人工发 H 得到 C，实发序为 2。再发 G 得到 B，实发序为 3。
7. 左幕从游标 0 得到 A 和 B，下一游标为 3。右幕得到 C，下一游标为 2。
8. 场务用原结场请求号再办，签存按实发序排列的 A、C、B。同一提交封闭本场。
9. 以同一数据库重开，用场号或结场号取得同一原件。

## JSON HTTP

所有操作使用 `POST`、`Content-Type: application/json` 和 UTF-8 JSON 对象。成功返回 200 与结果对象，业务错误返回含 `error` 的对象。编号和文本文字区分大小写，必填文本不能全为空白。

| 路径 | 输入字段 | 成功结果 |
| --- | --- | --- |
| `/draft` | `draft_id`、`cards`、`groups`、`order` | 草稿号和校验后的发行序 |
| `/issue` | `draft_id`、`request_id`，或单独的 `edition_id` | 固定发行件，含 `edition_id`、`draft_id`、`order`、`groups`、`cards` |
| `/open` | `show_id`、`edition_id`、`bindings`、`required_cards` | 场号、绑定发行号和运行状态 |
| `/key` | `show_id`、`key_id`、`request_id` | 直接键的实际发出首执 |
| `/send` | `show_id`、`request_id`，再给 `group` 或 `cards` 其中一项 | 人工实发首执 |
| `/inbox` | `show_id`、`seat`、`after` | 本席 `items`、`next_cursor` 和查询身份 |
| `/close` | `show_id`、`request_id` | `archive_id`、`show_id`、`edition_id`、按实发序冻结的 `sends` |
| `/archive_read` | 单独的 `show_id` 或 `archive_id` | 同一份固定结场件 |

草稿卡包含 `card_id`、`text` 和 `seat`。组是从组号到非空且无重复的本稿卡号数组的对象。`order` 必须完整列出每张卡各一次。开场绑定是从键号到组引用的对象，必发卡是卡引用数组。组和卡可以使用本版简写字符串，也可以使用含 `edition_id` 和 `group_id` 或 `card_id` 的对象。人工 `cards` 是非空数组。即使卡号相同，显式引用另一版也会退回整次请求。

发行位置 `position` 和实发位置 `seq` 均从 1 起。候选按 `position` 排列，跳过本场已发卡，取第一张可用卡。请求中的数组来序保留用于复领对比。实发首执载有卡文、席位、请求号、发出方式及 `source`，其中 `source` 记录发行号、草稿号和原卡号。每张卡每场只能实发一次，失败不占 `seq`。`after` 为非负整数，以 `seq > after` 取本席实发。空页返回原游标，席位按开场绑定的发行件识别。结场以必发卡号和实际已发卡号的集合差核对欠件，签存摘要保留各条实发原件。给定相同数据库状态和受理次序，计算结果可复现。

发行和结场请求号分别在各自业务内全局使用，人工和直接键共用本场发出请求号。同号同参可以复领首次结果，改参返回 409。运行场可重复领取同一配置，已结束场号不能重新开场。结场后新发拒绝，人工原号仍可复领，直接键入口返回 409。对已签场提交尚未占用的结场请求号会返回并关联原件。欠件、耗尽和状态冲突返回 409，缺失资源返回 404，无效业务字段、未绑定键和越版引用返回 422，JSON 传输错误返回 400。

`scripts/` 校验整稿，`editions/` 保存版本与出处，`control/` 管理场次与单键，`dispatch/` 记录实发及首执，`readback/` 提供席位取阅和结场。命令在单个 SQLite 写事务中提交关联记录，读请求使用一个已提交快照。
