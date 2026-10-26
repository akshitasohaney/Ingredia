function [meanScore, normalizedScore, riskBand] = ingredient_score(values)
%INGREDIENT_SCORE Example Ingredia calculation called from the Python API.
% VALUES must be a non-empty vector with values from 0 through 1.

    validateattributes(values, {'numeric'}, {'vector', 'nonempty', 'real', ...
        'finite', '>=', 0, '<=', 1}, mfilename, 'values');
    meanScore = mean(values);
    normalizedScore = 100 * meanScore;

    if meanScore < 0.34
        riskBand = "low";
    elseif meanScore < 0.67
        riskBand = "moderate";
    else
        riskBand = "high";
    end
end
