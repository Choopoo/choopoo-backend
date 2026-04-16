package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
)

// formula_json grammar:
//
//   leaf    := {"indicator_code": "..."} | {"scalar": <number>}
//   compose := {"op": "subtract"|"add"|"divide"|"multiply", "left": <expr>, "right": <expr>}
//   expr    := leaf | compose
//
// Composite indicator stored on the catalog OR tenant has formula_json non-null.
// Direct-reading indicators (formula_json IS NULL) resolve to the latest reading.

type evalNode struct {
	Op            string          `json:"op,omitempty"`
	Left          json.RawMessage `json:"left,omitempty"`
	Right         json.RawMessage `json:"right,omitempty"`
	IndicatorCode string          `json:"indicator_code,omitempty"`
	Scalar        *float64        `json:"scalar,omitempty"`
}

// evalFormula recursively reduces a formula_json tree to a float.
// Indicator-code leaves are resolved to the latest reading (catalog or tenant).
func evalFormula(ctx context.Context, tx *sql.Tx, raw json.RawMessage) (float64, error) {
	var n evalNode
	if err := json.Unmarshal(raw, &n); err != nil {
		return 0, fmt.Errorf("formula parse: %w", err)
	}
	if n.IndicatorCode != "" {
		v, _, err := latestReadingByCode(ctx, tx, n.IndicatorCode)
		return v, err
	}
	if n.Scalar != nil {
		return *n.Scalar, nil
	}
	if n.Op == "" {
		return 0, fmt.Errorf("formula node has neither op nor leaf")
	}
	left, err := evalFormula(ctx, tx, n.Left)
	if err != nil {
		return 0, err
	}
	right, err := evalFormula(ctx, tx, n.Right)
	if err != nil {
		return 0, err
	}
	switch strings.ToLower(n.Op) {
	case "subtract":
		return left - right, nil
	case "add":
		return left + right, nil
	case "multiply":
		return left * right, nil
	case "divide":
		if right == 0 {
			return 0, fmt.Errorf("divide by zero")
		}
		return left / right, nil
	default:
		return 0, fmt.Errorf("unknown op: %s", n.Op)
	}
}

// latestReadingByCode resolves an indicator code to its newest numeric reading.
// Looks up tenant indicators first (tenant overrides take precedence implicitly
// because tenant-private indicators write to tenant_indicator_readings); if not
// found, falls back to catalog readings.
func latestReadingByCode(ctx context.Context, tx *sql.Tx, code string) (float64, *string, error) {
	// Tenant private indicator?
	var tID sql.NullInt64
	var tFormula sql.NullString
	_ = tx.QueryRowContext(ctx,
		`SELECT id, formula_json FROM tenant_indicator WHERE code = $1`, code).Scan(&tID, &tFormula)
	if tID.Valid {
		// Composite tenant indicator: recursively evaluate its formula.
		if tFormula.Valid {
			v, err := evalFormula(ctx, tx, json.RawMessage(tFormula.String))
			if err != nil {
				return 0, nil, err
			}
			return v, nil, nil
		}
		var v float64
		var ts sql.NullTime
		err := tx.QueryRowContext(ctx,
			`SELECT value, ts FROM tenant_indicator_readings
			   WHERE tenant_indicator_id = $1 ORDER BY ts DESC LIMIT 1`, tID.Int64,
		).Scan(&v, &ts)
		if err == nil {
			s := ts.Time.UTC().Format("2006-01-02T15:04:05Z")
			return v, &s, nil
		}
		if err != sql.ErrNoRows {
			return 0, nil, err
		}
		return 0, nil, fmt.Errorf("no readings for tenant indicator %q", code)
	}

	// Catalog indicator: use catalog id, then global_indicator_readings.
	var cID sql.NullInt64
	var formula sql.NullString
	err := tx.QueryRowContext(ctx,
		`SELECT id, formula_json FROM catalog_indicator_template WHERE code = $1`, code).Scan(&cID, &formula)
	if err == sql.ErrNoRows {
		return 0, nil, fmt.Errorf("indicator code not found: %q", code)
	}
	if err != nil {
		return 0, nil, err
	}

	// Composite catalog indicators (formula present) recursively evaluate.
	if formula.Valid {
		v, err := evalFormula(ctx, tx, json.RawMessage(formula.String))
		if err != nil {
			return 0, nil, err
		}
		return v, nil, nil
	}

	var v float64
	var ts sql.NullTime
	err = tx.QueryRowContext(ctx,
		`SELECT value, ts FROM global_indicator_readings
		   WHERE indicator_id = $1 ORDER BY ts DESC LIMIT 1`, cID.Int64,
	).Scan(&v, &ts)
	if err == sql.ErrNoRows {
		return 0, nil, fmt.Errorf("no readings for catalog indicator %q", code)
	}
	if err != nil {
		return 0, nil, err
	}
	s := ts.Time.UTC().Format("2006-01-02T15:04:05Z")
	return v, &s, nil
}
