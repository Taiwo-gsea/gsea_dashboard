# GSEA Dashboard — User Study Questionnaire
## Appendix D: Evaluation Instrument

**Study title:** Evaluation of the GSEA Interactive Dashboard for Green Software Engineering Analysis  
**Module:** 6G7V0007 MSc Computer Science Project  
**Institution:** Manchester Metropolitan University  
**Ethics approval reference:** *(insert before distribution)*

---

### Participant Information

| Field | Response |
|-------|----------|
| Participant ID (anonymised) | P___ |
| Date | |
| Session duration (approx.) | |
| Role | ☐ Software Engineer  ☐ Researcher  ☐ Student  ☐ Other: ___ |
| Years of experience in software development | ☐ <1  ☐ 1–3  ☐ 3–7  ☐ 7+ |
| Prior knowledge of SCI / green software | ☐ None  ☐ Basic  ☐ Intermediate  ☐ Expert |

---

## PART 1 — Task Scenarios

*Complete the following tasks using the GSEA Dashboard. The observer will note completion time and errors. Think aloud where possible.*

### Task 1 — SCI Score Calculation
> Navigate to the **SCI Calculator**. Using the following values, calculate an SCI score:  
> E = 0.5 kWh, I = UK grid, M = cloud_vm_small, R = 1000 API calls.  
> Record the SCI score: ___________

- ☐ Completed successfully  ☐ Completed with assistance  ☐ Could not complete
- Time taken: _______ seconds
- Errors observed: _______________

### Task 2 — Energy Trend Analysis
> Navigate to **Energy Trend Analysis** and load the GMT sample data.  
> Enable the moving average. Identify whether the SCI trend is improving or worsening.  
> State your finding: ___________

- ☐ Completed successfully  ☐ Completed with assistance  ☐ Could not complete
- Time taken: _______ seconds

### Task 3 — Region Comparison
> Navigate to **Carbon Intensity Map**. Using E = 0.5 kWh, M = 10000 gCO₂eq, R = 1000,  
> compare UK vs France. What percentage SCI improvement does France offer?  
> Answer: ___________

- ☐ Completed successfully  ☐ Completed with assistance  ☐ Could not complete

### Task 4 — Data Upload
> Navigate to **Data Ingestion**. Upload the provided `gmt_sample.csv` file.  
> Report how many records were parsed: ___________

- ☐ Completed successfully  ☐ Completed with assistance  ☐ Could not complete

### Task 5 — NLP Extraction
> Navigate to **NLP Extraction**. Paste the sample text provided and run extraction.  
> Accept all CARBON_METRIC entities and reject any SOFTWARE_TOOL entities.

- ☐ Completed successfully  ☐ Completed with assistance  ☐ Could not complete

---

## PART 2 — System Usability Scale (SUS)

*Source: Brooke (1996). For each statement, circle one number from 1 (Strongly Disagree) to 5 (Strongly Agree).*

| # | Statement | SD | | | | SA |
|---|-----------|----|-|-|-|----|
| 1 | I think that I would like to use this system frequently. | 1 | 2 | 3 | 4 | 5 |
| 2 | I found the system unnecessarily complex. | 1 | 2 | 3 | 4 | 5 |
| 3 | I thought the system was easy to use. | 1 | 2 | 3 | 4 | 5 |
| 4 | I think that I would need support to be able to use this system. | 1 | 2 | 3 | 4 | 5 |
| 5 | I found the various functions in this system were well integrated. | 1 | 2 | 3 | 4 | 5 |
| 6 | I thought there was too much inconsistency in this system. | 1 | 2 | 3 | 4 | 5 |
| 7 | I would imagine that most people would learn to use this system quickly. | 1 | 2 | 3 | 4 | 5 |
| 8 | I found the system very cumbersome to use. | 1 | 2 | 3 | 4 | 5 |
| 9 | I felt very confident using the system. | 1 | 2 | 3 | 4 | 5 |
| 10 | I needed to learn a lot of things before I could get going with this system. | 1 | 2 | 3 | 4 | 5 |

**SUS Score Calculation:**
- Odd items (1,3,5,7,9): score = response − 1
- Even items (2,4,6,8,10): score = 5 − response
- SUS = sum of all adjusted scores × 2.5
- **Total SUS Score: _____ / 100**

| SUS Score | Adjective Rating | Grade |
|-----------|-----------------|-------|
| ≥ 90 | Best imaginable | A+ |
| 80–89 | Excellent | A |
| 70–79 | Good | B |
| 60–69 | OK | C |
| 50–59 | Poor | D |
| < 50 | Awful | F |

*Target for 95% dissertation grade: Mean SUS ≥ 68 (above industry average of 68, Sauro & Lewis 2016).*

---

## PART 3 — Domain-Specific Questions

*Rate each item from 1 (Not at all) to 5 (Completely).*

| # | Question | 1 | 2 | 3 | 4 | 5 |
|---|----------|---|---|---|---|---|
| D1 | The SCI formula breakdown (E×I+M/R) helped me understand where carbon comes from. | | | | | |
| D2 | The proxy metric charts made energy consumption patterns easy to understand. | | | | | |
| D3 | The carbon intensity map helped me appreciate the impact of deployment region. | | | | | |
| D4 | The NLP extraction feature would save time when reviewing GSE papers. | | | | | |
| D5 | The comparative analysis view clearly showed which configuration was greener. | | | | | |
| D6 | I would use this dashboard to make real software deployment decisions. | | | | | |
| D7 | The colour scheme made charts easy to read (including for colour-blind users). | | | | | |
| D8 | The dashboard filled a gap that existing tools (GMT, CodeCarbon) do not cover. | | | | | |

---

## PART 4 — Open-Ended Feedback

**Q1. What did you find most useful about the dashboard?**

_______________________________________________

**Q2. What was the most confusing or frustrating aspect?**

_______________________________________________

**Q3. What feature would you most like to see added?**

_______________________________________________

**Q4. Compared to tools you have used before (e.g., CodeCarbon, GMT), how does GSEA Dashboard compare?**

☐ Much worse  ☐ Worse  ☐ About the same  ☐ Better  ☐ Much better

**Comments:** _______________________________________________

**Q5. Any additional comments?**

_______________________________________________

---

## PART 5 — Feature Usefulness Ranking

*Rank the following features from 1 (most useful) to 8 (least useful):*

| Feature | Rank (1–8) |
|---------|-----------|
| SCI Score Calculator | |
| Energy Trend Analysis | |
| Proxy Metric Visualisation | |
| Carbon Intensity Map | |
| Data Ingestion (GMT/CodeCarbon) | |
| NLP Entity Extraction | |
| Comparative Analysis | |
| Reports & Export | |

---

## Observer Notes

| Field | Notes |
|-------|-------|
| Critical incidents | |
| Navigation errors | |
| Points of confusion | |
| Positive reactions | |
| Suggested improvements | |

---

*Thank you for participating. Your feedback directly informs the dissertation evaluation (Chapter 6) and future development of the GSEA Dashboard.*

*Data will be anonymised and stored securely. No personally identifiable information will appear in the dissertation.*

---

**References**
- Brooke, J. (1996). SUS: A 'quick and dirty' usability scale. In P. Jordan et al. (Eds.), *Usability Evaluation in Industry* (pp. 189–194). Taylor & Francis.
- Sauro, J., & Lewis, J. R. (2016). *Quantifying the User Experience: Practical Statistics for User Research* (2nd ed.). Morgan Kaufmann.
