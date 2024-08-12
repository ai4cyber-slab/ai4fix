import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import cross_val_score
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import Ridge
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.ensemble import RandomForestRegressor


data_file_path = r'path/to/patch_generation_data.csv'
data = np.genfromtxt(data_file_path, delimiter=',', skip_header=1)

x = data[:, 0].reshape(-1, 1) 
y = data[:, 1]


models = {
    'Linear': LinearRegression(),
    'Polynomial (degree 3)': make_pipeline(PolynomialFeatures(degree=3), LinearRegression()),
    'Polynomial (degree 2)': make_pipeline(PolynomialFeatures(degree=2), LinearRegression()),
    # 'Ridge': Ridge(alpha=1.0),
    # 'Decision Tree': DecisionTreeRegressor(random_state=42),
    # 'Gradient Boosting': GradientBoostingRegressor(n_estimators=100, random_state=42),
    # 'Random Forest': RandomForestRegressor(n_estimators=100, random_state=42)

}

cv_scores = {}
for name, model in models.items():
    scores = cross_val_score(model, x, y, cv=5, scoring='neg_mean_squared_error')
    cv_scores[name] = np.mean(-scores)

best_model_name = min(cv_scores, key=cv_scores.get)
best_model = models[best_model_name]
best_model.fit(x, y)

for name, score in cv_scores.items():
    print(f"{name}: {score:.4f} (MSE)")

print(f"Best model: {best_model_name}")


x_new = np.array([[10]])
predicted_time_10KLOC = best_model.predict(x_new)[0]
print(f"Estimated time to generate patch for 10KLOC: {predicted_time_10KLOC} seconds")


plt.scatter(x, y, color='blue', label='Data points')


x_plot = np.linspace(min(x), 10, 100).reshape(-1, 1)
y_plot = best_model.predict(x_plot)
plt.plot(x_plot, y_plot, color='red', label=f'Best fit ({best_model_name})')


plt.scatter([10], [predicted_time_10KLOC], color='green', label='Prediction for 10 KLOC', zorder=5)

plt.xlabel('Code Size (KLOC)')
plt.ylabel('Patch Generation Time (seconds)')
plt.legend()
plt.show()



# # Extrapolation
# data_points = np.genfromtxt(data_file_path, delimiter=',', skip_header=1)
# x = data_points[:, 0]  # Code sizes in KLOC
# y = data_points[:, 1]  # Times in seconds

# # Fit a linear regression model
# coefficients = np.polyfit(x, y, 1)
# linear_model = np.poly1d(coefficients)

# # Predict time for 10 KLOC
# predicted_time_10KLOC = linear_model(10)
# print(f"data gathered: {data_points}\n")
# print(f"Estimated time to generate patch for 10KLOC using Extrapolation: {predicted_time_10KLOC} seconds")

