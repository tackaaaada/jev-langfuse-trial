# 正確性の3信号による比較（10件）

2026-09-19に、[既存の10件の合成データ](../data/semantic_equivalence_v0.json)を再評価しました。Jevあり条件は`correctness-triad-v1`、Langfuseの`Check Correctness` Evaluatorはバージョン4です。実行時のベンチマークID・トレースIDは公開していません。

## Jevで定義した正確性の3信号

| 信号 | 型 | 定義 | 最終Evaluatorでの扱い |
| --- | --- | --- | --- |
| `is_correct` | Noul | 期待回答の重要な事実・制約・結論・関係を回答が保持する確率 | 0.5以上を一次trueに変換するが、参考情報に留める |
| `primary_correctness_issue` | Choice | 主な差分を`no_material_issue`、欠落、矛盾・制約変更、根拠のない追加、関係・結論変更、検証不能から一つ選ぶ | 主因分類。複数の問題がある場合も一つしか選ばない |
| `correctness_materiality` | Score | 0: 差分なし、1: 非重要な差分、2: 重要な差分、3: 中心的または複数の重要な差分 | booleanの部分点ではなく、差分の大きさの参考情報 |

Jevありではこの3信号を`jev_correctness_assessment`として`Check Correctness`へ渡しました。Jevなしでは同じ回答・期待回答だけを`Check Correctness Without Jev`へ渡しました。人手ラベルはEvaluatorへ渡していません。

## 結果

| ケース | 人手 | Noul（確率 / 判定） | Choice | Score | GPT-4o: Jevあり | GPT-4o: Jevなし |
| --- | --- | --- | --- | ---: | --- | --- |
| equivalent-shop-guide | true | 0.97 / true | no_material_issue | 0.16 | true | true |
| equivalent-reordered-policy | true | 0.93 / true | no_material_issue | 0.40 | true | true |
| equivalent-structured-answer | true | 0.93 / true | no_material_issue | 0.63 | true | true |
| equivalent-calculation | true | 0.58 / true | no_material_issue | 0.79 | true | true |
| missing-refund-exception | false | 0.03 / false | missing_required_detail | 2.00 | false | false |
| contradicted-booking-deadline | false | 0.03 / false | contradicted_or_altered_constraint | 2.30 | false | false |
| unsupported-shipping-claim | false | 0.82 / true | unsupported_or_misleading_addition | 1.87 | true | true |
| changed-relationship | false | 0.01 / false | contradicted_or_altered_constraint | 2.97 | false | false |
| equivalent-clarifying-addition | true | 0.88 / true | unsupported_or_misleading_addition | 1.09 | true | true |
| boundary-proportional-rate | true | 0.94 / true | no_material_issue | 0.33 | true | true |

トレースURLと内部IDは公開用の記録から除外しています。ローカル実行時は、出力される`benchmark_id`でLangfuseを検索してください。

## 読み取れること

今回もJev、JevありGPT-4o、JevなしGPT-4oは、人手ラベルと9/10件で一致しました。`unsupported-shipping-claim`だけを3系統ともtrueにし、根拠のない配送条件の追加を重要でない追加情報として扱いました。3信号を追加しても、最終booleanは前回と変わりませんでした。

ただし、そのケースでJevの内部信号は一枚岩ではありません。Noulはtrueを0.82とした一方、Choiceは`unsupported_or_misleading_addition`を0.94で選び、Scoreは1.87で「重要な差分」に近い値を返しました。GPT-4oはJevあり条件でこの追加を非重要と判断してtrueにし、Jevなし条件もtrueでした。これは、追加したChoice・Scoreが最終判定を自動的に上書きせず、参考情報として扱われている実例です。

`equivalent-clarifying-addition`では、Noulはtrue 0.88、Choiceは`unsupported_or_misleading_addition` 0.54と`no_material_issue` 0.45の接戦、Scoreは1.09でした。Choiceの単一ラベルだけでルーティングすると、このような境界例を過度に扱うおそれがあります。Choiceのconfidenceや分布、ScoreとNoulを併せて確認する必要があります。

`changed-relationship`は人手では関係変更と分類したものの、Jevは`contradicted_or_altered_constraint`を主因に選びました。どちらも正確性の不一致を示すため最終booleanには影響しませんが、ラベルをEvaluatorの振り分けに使う場合は、カテゴリ定義が重なっていることを示しています。まずは全ケースを同じ正確性Evaluatorへ渡し、ラベルは分析・説明用に使うのが妥当です。

この10件は合成の小標本で、モデルの精度・独立性・最適な閾値を結論づける材料ではありません。次は、各カテゴリを増やし、複数人のラベルと実運用データを含む固定セットで、Choiceの混同行列、Scoreの閾値、Jevあり／なしの差を検証します。
