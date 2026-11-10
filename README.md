# Credit Risk Model Validation & Decisioning Workbench

**An independent Financial Data Science project using Python, Machine Learning and Statistical Model Validation.**

## 1. Project Overview

This project aims to develop and validate credit risk models to assess the probability of customer default and support data-driven lending decisions.

The project explores traditional statistical modelling techniques alongside machine learning approaches, with a focus on model performance, reliability, explainability and financial decision-making.

The objective is to understand how credit risk models can be evaluated and how their outputs can support responsible lending decisions.

## 2. Project Objectives

- Develop a Probability of Default (PD) prediction model.
- Implement a traditional Logistic Regression model.
- Develop a machine learning challenger model using XGBoost.
- Evaluate model discrimination and predictive performance.
- Assess model calibration and stability.
- Analyse model explainability and feature importance.
- Explore credit decision thresholds and financial implications.
- Develop an interactive dashboard for model assessment.

## 3. Dataset

**Dataset:** Default of Credit Card Clients

**Source:** UCI Machine Learning Repository

**Dataset characteristics:**
- 30,000 observations.
- 23 explanatory variables.
- Historical credit card default information.
- Binary target variable representing default payment status.

The dataset will be used strictly for educational and analytical purposes.

## 4. Technology Stack

| Technology | Application |
|---|---|
| Python | Data analysis and modelling |
| Pandas & NumPy | Data processing |
| Scikit-learn | Statistical modelling and validation |
| XGBoost | Challenger model |
| Matplotlib & Seaborn | Data visualisation |
| SHAP | Model explainability |
| SQL | Data querying |
| Streamlit | Interactive dashboard |
| Git & GitHub | Version control |

## 5. Model Validation Framework

The planned validation framework includes:

- Discrimination: ROC-AUC, Gini and KS statistics.
- Calibration: Brier score and calibration curves.
- Stability: Population Stability Index (PSI) and feature drift.
- Explainability: SHAP analysis.
- Decisioning: Risk thresholds and cost-sensitive analysis.

## 6. Project Structure

```text
credit-risk-model-validation/
│
├── data/
│   ├── raw/
│   └── processed/
│
├── notebooks/
│
├── src/
│
├── models/
│
├── reports/
│
├── dashboard/
│
├── tests/
│
├── README.md
└── requirements.txt
```

## 7. Expected Outcomes

- A reproducible credit risk modelling pipeline.
- Comparative evaluation of statistical and machine learning models.
- A documented model validation framework.
- Financial decisioning analysis.
- An interactive model validation dashboard.
- Technical documentation and business recommendations.

## 8. Limitations

The project uses a publicly available historical dataset. Results should not be interpreted as evidence of current banking portfolio performance or production model suitability.

Model limitations, assumptions, data quality issues and validation constraints will be documented throughout development.

## 9. Project Status

**Status: In Progress**

This project is being developed as an independent educational portfolio project.

---

**Author:** Nayana Jagadish  
**Focus Areas:** Financial Data Science | Credit Risk Analytics | Model Validation | Business Analytics
