# Jevなしの3回評価と比較

2026-09-19。[同じ長文ペア](../data/long_semantic_match.json)をGPT-4oだけで3回評価しました。

## 条件

- モデル: `openai / gpt-4o`。元の質問文は、Jevあり条件と同様に判定に渡していません。
- 回答・期待回答・意味的一致の基準・例・BOOLEAN形式はJevあり条件と共通です。
- Jevの一次結果、一次結果を参照する指示、判定理由にJevへの賛否を求める指示を除去しました。
- Evaluatorは`Check Correctness Without Jev`、対象Observationは`finalize-answer-without-jev`です。既存のJevありEvaluatorとルールは変更していません。
- TypeSafeへのAPI呼び出しはありません。Jevのスコア・結果を入力やmetadataに含めていません。

## 結果

| 回 | Jevあり（前回） | Jevなし（今回） |
| --- | --- | --- |
| 1 | true（Jev確率0.97） | true |
| 2 | true（Jev確率0.97） | true |
| 3 | true（Jev確率0.97） | true |

## 読み取れること

今回の1ペアでは、Jevあり・なし各3回とも最終判定はtrueでした。GPT-4oはJevの結果を渡さなくても意味的一致と判断できました。
各理由は営業時間、休業日、商品閲覧の予約不要、相談の予約・料金、キャンセル、駐車場などを比較しています。理由の詳しさには回ごとの差があります。

一方、Jevに追従しないという一般的な性質、Jevによる精度改善、Jevが誤ったときにGPT-4oが訂正できることは、今回の一致例だけでは確認できません。3回は同一ペアの反復であり、異なる3件の正解率ではありません。
また、前回の短文falseから今回trueになった原因を文章の長さだけには帰せません。店名を明示し、内容自体も変更しています。

## 再実行

```bash
uv run python -m src.no_jev_experiment --repeat 3
```

比較用Evaluatorとルールは作成・有効化済みです。再実行するとGPT-4oのAPI利用料が発生します。
設定は`config/langfuse/evaluator-without-jev.json`と`config/langfuse/rule-without-jev.json`に保存しています。別環境ではEvaluatorを作成して返されたIDをルールに設定する必要があります。

## 判定理由（保存された原文）

### 1回目

The actual output successfully matches the material meaning of the expected output. Here are the key points:

1. **Store Hours and Closure Days**:
   - The actual output states the shop opens at 10 AM and closes at 6 PM, aligning with the expected hours.
   - Both texts confirm that the store is closed every Wednesday and also on Wednesdays if they coincide with public holidays.

2. **Visiting the Store**:
   - The actual highlights that a reservation isn't needed for simply viewing products, synonymous with the expected text's 'no reservation required for product browsing'.

3. **Consultation Details**:
   - Both outputs specify that individual consultations with staff require a reservation by phone, made before 5 PM on the day before the desired visit.
   - It is clearly stated in both cases that the consultations are free of charge.
   - Cancellation of reservations must also be done by 5 PM the day before, via phone.

4. **Parking Information**:
   - Both outputs note the absence of dedicated parking spaces, recommending the use of nearby paid parking if arriving by car.
   
There is no alteration, misleading addition, or missing details that change the essential meaning of the expected output. Thus, the score is true.

### 2回目

Both the actual and expected outputs describe the operational details of a shop with regard to its opening times, holidays, appointment system, and parking information. Key points include:

1. **Opening Hours**: Both specify the shop opens at 10 AM and closes at 6 PM.
2. **Holidays**: Both mention regular closure on Wednesdays, including when a Wednesday coincides with a holiday.
3. **Appointments**: Both agree that browsing does not require an appointment, whereas consultations with staff require prior booking by phone before 5 PM on the day before the intended visit.
4. **Consultation Cost & Cancellation**: Both clarify consultations are free and include information about canceling appointments by 5 PM the day before.
5. **Parking**: Both note the absence of a dedicated parking facility, advising using nearby paid lots.

No material differences or contradictions are detected in semantic meaning between outputs.

### 3回目

The semantic comparison evaluates both the expected and actual outputs to determine equivalence in meaning: 

### Material Claims, Facts, and Conclusions in Expected Output:
1. **Operating Hours**: Open from 10 AM to 6 PM.
2. **Weekly Off**: The shop is closed on Wednesdays, including public holidays falling on Wednesday.
3. **Unscheduled Visits**: No appointment required to visit for viewing products.
4. **Staff Consultation**:
    - Requires reservation.
    - Reservations must be made by 5 PM the day before the desired visit.
    - Consultations are free.
5. **Cancellations**: Must be made by 5 PM the day before.
6. **Parking**: No dedicated parking; nearest paid parking to be used.

### Analysis of Actual Assistant Output Against Expected Requirements:
- **Operating Hours**: Matched description of opening from 10 AM to 6 PM.
- **Weekly Off**: Clearly stated closure on Wednesdays, including holidays.
- **Unscheduled Visits**: Emphasized no appointment requirement to view items.
- **Staff Consultation**:
  - Stipulated need for reservation.
  - Accurately detailed the need to book by 5 PM, a day in advance.
  - Noted consultations are free of charge.
- **Cancellations**: Informed about the cancellation policy matching the expected detail.
- **Parking**: Addressed absence of on-site parking and directed to local paid parking appropriately.

### Conclusion:
All material elements and relationships between facts and constraints are preserved with no contradictions. The actual output provides a full match to the expected output's semantic content.

前回は[Jevありのレポート](long-answer-three-runs.md)を参照してください。トレースURL・内部ID・生の実行記録は公開用のリポジトリから除外しています。
