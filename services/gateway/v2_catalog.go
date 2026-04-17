package main

import (
	"database/sql"
	"encoding/json"
	"log"
	"net/http"
	"strconv"
)

// =====================================================================
// catalog browse — global, read-only
// =====================================================================

type catalogMaterial struct {
	ID         int64   `json:"id"`
	Code       string  `json:"code"`
	Name       string  `json:"name"`
	NameCN     *string `json:"name_cn"`
	Unit       string  `json:"unit"`
	Category   *string `json:"category"`
	Volatility *string `json:"volatility"`
	SupplyRisk *string `json:"supply_risk"`
}

type catalogProduct struct {
	ID                int64   `json:"id"`
	FamilyID          *int64  `json:"family_id"`
	Code              string  `json:"code"`
	Name              string  `json:"name"`
	NameCN            *string `json:"name_cn"`
	DefaultRegionCode *string `json:"default_region_code"`
	Description       *string `json:"description"`
}

type catalogIndicator struct {
	ID             int64           `json:"id"`
	Code           string          `json:"code"`
	Name           *string         `json:"name"`
	NameCN         *string         `json:"name_cn"`
	Kind           string          `json:"kind"`
	SubjectKind    string          `json:"subject_kind"`
	SubjectCode    *string         `json:"subject_code"`
	RegionCode     *string         `json:"region_code"`
	Unit           string          `json:"unit"`
	CadenceMinutes int             `json:"cadence_minutes"`
	SourceID       *int64          `json:"source_id"`
	FormulaJSON    json.RawMessage `json:"formula_json"`
	Description    *string         `json:"description"`
	DescriptionCN  *string         `json:"description_cn"`
}

func handleV2CatalogMaterials(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	rows, err := tx.QueryContext(r.Context(),
		`SELECT id, code, name, name_cn, unit, category, volatility, supply_risk
		   FROM catalog_raw_material ORDER BY category NULLS LAST, code`)
	if err != nil {
		log.Printf("catalog/materials: %v", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "query"})
		return
	}
	defer rows.Close()
	out := []catalogMaterial{}
	for rows.Next() {
		var m catalogMaterial
		var ncn, cat, vol, risk sql.NullString
		if err := rows.Scan(&m.ID, &m.Code, &m.Name, &ncn, &m.Unit, &cat, &vol, &risk); err != nil {
			continue
		}
		m.NameCN = nullStringPtr(ncn)
		m.Category = nullStringPtr(cat)
		m.Volatility = nullStringPtr(vol)
		m.SupplyRisk = nullStringPtr(risk)
		out = append(out, m)
	}
	writeJSON(w, http.StatusOK, out)
}

func handleV2CatalogProducts(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	rows, err := tx.QueryContext(r.Context(),
		`SELECT id, family_id, code, name, name_cn, default_region_code, description
		   FROM catalog_finished_product ORDER BY family_id, code`)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	defer rows.Close()
	out := []catalogProduct{}
	for rows.Next() {
		var p catalogProduct
		var fid sql.NullInt64
		var ncn, drc, desc sql.NullString
		if err := rows.Scan(&p.ID, &fid, &p.Code, &p.Name, &ncn, &drc, &desc); err != nil {
			continue
		}
		if fid.Valid {
			v := fid.Int64
			p.FamilyID = &v
		}
		p.NameCN = nullStringPtr(ncn)
		p.DefaultRegionCode = nullStringPtr(drc)
		p.Description = nullStringPtr(desc)
		out = append(out, p)
	}
	writeJSON(w, http.StatusOK, out)
}

func handleV2CatalogIndicators(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	rows, err := tx.QueryContext(r.Context(),
		`SELECT id, code, name, name_cn, kind, subject_kind, subject_code, region_code, unit,
		        cadence_minutes, source_id, formula_json, description, description_cn
		   FROM catalog_indicator_template ORDER BY kind, code`)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	defer rows.Close()
	out := []catalogIndicator{}
	for rows.Next() {
		var ind catalogIndicator
		var name, nameCN, subC, regC, desc, descCN sql.NullString
		var srcID sql.NullInt64
		var formula sql.NullString
		if err := rows.Scan(&ind.ID, &ind.Code, &name, &nameCN, &ind.Kind, &ind.SubjectKind,
			&subC, &regC, &ind.Unit, &ind.CadenceMinutes, &srcID, &formula, &desc, &descCN); err != nil {
			continue
		}
		ind.Name = nullStringPtr(name)
		ind.NameCN = nullStringPtr(nameCN)
		ind.SubjectCode = nullStringPtr(subC)
		ind.RegionCode = nullStringPtr(regC)
		ind.Description = nullStringPtr(desc)
		ind.DescriptionCN = nullStringPtr(descCN)
		if srcID.Valid {
			v := srcID.Int64
			ind.SourceID = &v
		}
		if formula.Valid {
			ind.FormulaJSON = json.RawMessage(formula.String)
		} else {
			ind.FormulaJSON = json.RawMessage("null")
		}
		out = append(out, ind)
	}
	writeJSON(w, http.StatusOK, out)
}

// =====================================================================
// tenant overlay — enable / override / private addition
// =====================================================================

type enableMaterialReq struct {
	CatalogRawMaterialID int64  `json:"catalog_raw_material_id"`
	Nickname             string `json:"nickname,omitempty"`
}

func handleV2TenantEnableMaterial(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	s := sessionFromContext(r.Context())
	var req enableMaterialReq
	if err := decodeJSON(r, &req); err != nil || req.CatalogRawMaterialID == 0 {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "catalog_raw_material_id required"})
		return
	}
	var nickname *string
	if req.Nickname != "" {
		nickname = &req.Nickname
	}
	if _, err := tx.ExecContext(r.Context(),
		`INSERT INTO tenant_raw_material_enablement (org_id, catalog_raw_material_id, nickname)
		 VALUES ($1, $2, $3)
		 ON CONFLICT (org_id, catalog_raw_material_id) DO UPDATE SET nickname = EXCLUDED.nickname`,
		s.OrgID, req.CatalogRawMaterialID, nickname); err != nil {
		log.Printf("enable material: %v", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
}

type createPrivateMaterialReq struct {
	Code          string          `json:"code"`
	Name          string          `json:"name"`
	NameCN        string          `json:"name_cn,omitempty"`
	Unit          string          `json:"unit,omitempty"`
	Category      string          `json:"category,omitempty"`
	UpstreamOfRef json.RawMessage `json:"upstream_of_ref,omitempty"`
}

func handleV2TenantCreateMaterial(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	s := sessionFromContext(r.Context())
	var req createPrivateMaterialReq
	if err := decodeJSON(r, &req); err != nil || req.Code == "" || req.Name == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "code+name required"})
		return
	}
	unit := req.Unit
	if unit == "" {
		unit = "CNY/ton"
	}
	var id int64
	var nameCN sql.NullString
	if req.NameCN != "" {
		nameCN = sql.NullString{String: req.NameCN, Valid: true}
	}
	var category sql.NullString
	if req.Category != "" {
		category = sql.NullString{String: req.Category, Valid: true}
	}
	var upstream interface{}
	if len(req.UpstreamOfRef) > 0 {
		upstream = string(req.UpstreamOfRef)
	}
	err := tx.QueryRowContext(r.Context(),
		`INSERT INTO tenant_raw_material (org_id, code, name, name_cn, unit, category, upstream_of_ref)
		 VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id`,
		s.OrgID, req.Code, req.Name, nameCN, unit, category, upstream,
	).Scan(&id)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	writeJSON(w, http.StatusOK, map[string]int64{"id": id})
}

type enableIndicatorReq struct {
	CatalogIndicatorTemplateID int64  `json:"catalog_indicator_template_id"`
	Role                       string `json:"role,omitempty"`
}

func handleV2TenantEnableIndicator(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	s := sessionFromContext(r.Context())
	var req enableIndicatorReq
	if err := decodeJSON(r, &req); err != nil || req.CatalogIndicatorTemplateID == 0 {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "catalog_indicator_template_id required"})
		return
	}
	var role sql.NullString
	if req.Role != "" {
		role = sql.NullString{String: req.Role, Valid: true}
	}
	if _, err := tx.ExecContext(r.Context(),
		`INSERT INTO tenant_indicator_enablement (org_id, catalog_indicator_template_id, role)
		 VALUES ($1, $2, $3)
		 ON CONFLICT (org_id, catalog_indicator_template_id) DO UPDATE SET role = EXCLUDED.role`,
		s.OrgID, req.CatalogIndicatorTemplateID, role); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
}

type overrideIndicatorReq struct {
	CatalogIndicatorTemplateID int64           `json:"catalog_indicator_template_id"`
	FormulaJSONOverride        json.RawMessage `json:"formula_json_override,omitempty"`
	CadenceOverride            *int            `json:"cadence_override,omitempty"`
	SourceOverride             *int64          `json:"source_override,omitempty"`
}

func handleV2TenantOverrideIndicator(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	s := sessionFromContext(r.Context())
	var req overrideIndicatorReq
	if err := decodeJSON(r, &req); err != nil || req.CatalogIndicatorTemplateID == 0 {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "catalog_indicator_template_id required"})
		return
	}
	var formula interface{}
	if len(req.FormulaJSONOverride) > 0 && string(req.FormulaJSONOverride) != "null" {
		formula = string(req.FormulaJSONOverride)
	}
	if _, err := tx.ExecContext(r.Context(),
		`INSERT INTO tenant_indicator_override (org_id, catalog_indicator_template_id,
		                                         formula_json_override, cadence_override, source_override)
		 VALUES ($1, $2, $3, $4, $5)
		 ON CONFLICT (org_id, catalog_indicator_template_id) DO UPDATE
		   SET formula_json_override = EXCLUDED.formula_json_override,
		       cadence_override = EXCLUDED.cadence_override,
		       source_override = EXCLUDED.source_override`,
		s.OrgID, req.CatalogIndicatorTemplateID, formula, req.CadenceOverride, req.SourceOverride); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
}

type createPrivateIndicatorReq struct {
	Code           string          `json:"code"`
	Kind           string          `json:"kind"`
	SubjectKind    string          `json:"subject_kind"`
	SubjectRef     json.RawMessage `json:"subject_ref,omitempty"`
	RegionCode     string          `json:"region_code,omitempty"`
	Unit           string          `json:"unit"`
	CadenceMinutes int             `json:"cadence_minutes,omitempty"`
	SourceRef      json.RawMessage `json:"source_ref,omitempty"`
	FormulaJSON    json.RawMessage `json:"formula_json,omitempty"`
	Description    string          `json:"description,omitempty"`
}

func handleV2TenantCreateIndicator(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	s := sessionFromContext(r.Context())
	var req createPrivateIndicatorReq
	if err := decodeJSON(r, &req); err != nil || req.Code == "" || req.Kind == "" || req.Unit == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "code, kind, unit required"})
		return
	}
	cadence := req.CadenceMinutes
	if cadence == 0 {
		cadence = 1440
	}
	var subj, src, formula interface{}
	if len(req.SubjectRef) > 0 {
		subj = string(req.SubjectRef)
	}
	if len(req.SourceRef) > 0 {
		src = string(req.SourceRef)
	}
	if len(req.FormulaJSON) > 0 && string(req.FormulaJSON) != "null" {
		formula = string(req.FormulaJSON)
	}
	var region, desc sql.NullString
	if req.RegionCode != "" {
		region = sql.NullString{String: req.RegionCode, Valid: true}
	}
	if req.Description != "" {
		desc = sql.NullString{String: req.Description, Valid: true}
	}
	var id int64
	err := tx.QueryRowContext(r.Context(),
		`INSERT INTO tenant_indicator
		   (org_id, code, kind, subject_kind, subject_ref, region_code, unit,
		    cadence_minutes, source_ref, formula_json, description)
		 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
		 RETURNING id`,
		s.OrgID, req.Code, req.Kind, req.SubjectKind, subj, region, req.Unit,
		cadence, src, formula, desc,
	).Scan(&id)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	writeJSON(w, http.StatusOK, map[string]int64{"id": id})
}

// =====================================================================
// tenant resolved views (composer)
// =====================================================================

type resolvedMaterial struct {
	Source     string  `json:"source"` // "catalog" | "private"
	ID         int64   `json:"id"`
	Code       string  `json:"code"`
	Name       string  `json:"name"`
	Nickname   *string `json:"nickname,omitempty"`
	Unit       string  `json:"unit"`
	Category   *string `json:"category"`
	Volatility *string `json:"volatility,omitempty"`
	SupplyRisk *string `json:"supply_risk,omitempty"`
}

// GET /api/v2/me/materials — enabled catalog (with nickname) ∪ private materials.
func handleV2MeMaterials(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())

	out := []resolvedMaterial{}

	rows, err := tx.QueryContext(r.Context(),
		`SELECT crm.id, crm.code, crm.name, crm.unit, crm.category, crm.volatility, crm.supply_risk,
		        trme.nickname
		   FROM tenant_raw_material_enablement trme
		   JOIN catalog_raw_material crm ON crm.id = trme.catalog_raw_material_id
		   ORDER BY crm.code`)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	for rows.Next() {
		var m resolvedMaterial
		var nick, cat, vol, risk sql.NullString
		if err := rows.Scan(&m.ID, &m.Code, &m.Name, &m.Unit, &cat, &vol, &risk, &nick); err != nil {
			continue
		}
		m.Source = "catalog"
		m.Category = nullStringPtr(cat)
		m.Volatility = nullStringPtr(vol)
		m.SupplyRisk = nullStringPtr(risk)
		m.Nickname = nullStringPtr(nick)
		out = append(out, m)
	}
	rows.Close()

	rows, err = tx.QueryContext(r.Context(),
		`SELECT id, code, name, unit, category FROM tenant_raw_material ORDER BY code`)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	for rows.Next() {
		var m resolvedMaterial
		var cat sql.NullString
		if err := rows.Scan(&m.ID, &m.Code, &m.Name, &m.Unit, &cat); err != nil {
			continue
		}
		m.Source = "private"
		m.Category = nullStringPtr(cat)
		out = append(out, m)
	}
	rows.Close()
	writeJSON(w, http.StatusOK, out)
}

type resolvedIndicator struct {
	Source         string          `json:"source"` // "catalog" | "catalog+override" | "private"
	ID             int64           `json:"id"`
	Code           string          `json:"code"`
	Name           *string         `json:"name,omitempty"`
	NameCN         *string         `json:"name_cn,omitempty"`
	Kind           string          `json:"kind"`
	SubjectKind    string          `json:"subject_kind"`
	SubjectCode    *string         `json:"subject_code,omitempty"`
	RegionCode     *string         `json:"region_code,omitempty"`
	Unit           string          `json:"unit"`
	CadenceMinutes int             `json:"cadence_minutes"`
	FormulaJSON    json.RawMessage `json:"formula_json"`
	Description    *string         `json:"description,omitempty"`
	DescriptionCN  *string         `json:"description_cn,omitempty"`
}

// GET /api/v2/me/indicators — enabled catalog (with overrides applied) ∪ private.
// Composer precedence: tenant_indicator > tenant_indicator_override > catalog.
func handleV2MeIndicators(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())

	out := []resolvedIndicator{}

	// Enabled catalog with overrides applied.
	rows, err := tx.QueryContext(r.Context(),
		`SELECT cit.id, cit.code, cit.name, cit.name_cn, cit.kind, cit.subject_kind, cit.subject_code,
		        cit.region_code, cit.unit,
		        COALESCE(tio.cadence_override, cit.cadence_minutes) AS cadence_minutes,
		        COALESCE(tio.formula_json_override, cit.formula_json) AS formula_json,
		        cit.description, cit.description_cn,
		        (tio.org_id IS NOT NULL) AS has_override
		   FROM tenant_indicator_enablement tie
		   JOIN catalog_indicator_template cit ON cit.id = tie.catalog_indicator_template_id
		   LEFT JOIN tenant_indicator_override tio
		          ON tio.catalog_indicator_template_id = cit.id
		   ORDER BY cit.kind, cit.code`)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	for rows.Next() {
		var ind resolvedIndicator
		var name, nameCN, subC, regC, desc, descCN, formula sql.NullString
		var hasOverride bool
		if err := rows.Scan(&ind.ID, &ind.Code, &name, &nameCN, &ind.Kind, &ind.SubjectKind,
			&subC, &regC, &ind.Unit, &ind.CadenceMinutes, &formula, &desc, &descCN, &hasOverride); err != nil {
			continue
		}
		ind.Name = nullStringPtr(name)
		ind.NameCN = nullStringPtr(nameCN)
		ind.SubjectCode = nullStringPtr(subC)
		ind.RegionCode = nullStringPtr(regC)
		ind.Description = nullStringPtr(desc)
		ind.DescriptionCN = nullStringPtr(descCN)
		if formula.Valid {
			ind.FormulaJSON = json.RawMessage(formula.String)
		} else {
			ind.FormulaJSON = json.RawMessage("null")
		}
		if hasOverride {
			ind.Source = "catalog+override"
		} else {
			ind.Source = "catalog"
		}
		out = append(out, ind)
	}
	rows.Close()

	rows, err = tx.QueryContext(r.Context(),
		`SELECT id, code, kind, subject_kind, region_code, unit, cadence_minutes,
		        formula_json, description
		   FROM tenant_indicator ORDER BY kind, code`)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	for rows.Next() {
		var ind resolvedIndicator
		var regC, desc, formula sql.NullString
		if err := rows.Scan(&ind.ID, &ind.Code, &ind.Kind, &ind.SubjectKind,
			&regC, &ind.Unit, &ind.CadenceMinutes, &formula, &desc); err != nil {
			continue
		}
		ind.Source = "private"
		ind.RegionCode = nullStringPtr(regC)
		ind.Description = nullStringPtr(desc)
		if formula.Valid {
			ind.FormulaJSON = json.RawMessage(formula.String)
		} else {
			ind.FormulaJSON = json.RawMessage("null")
		}
		out = append(out, ind)
	}
	rows.Close()
	writeJSON(w, http.StatusOK, out)
}

// helper for response sources field; intentionally exported-style name
var _ = strconv.Itoa
