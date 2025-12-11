-- -----------------------------------------------------------
-- normalize_price_unit.sql
-- PostgreSQL function to normalize price_unit strings
-- Idempotent: uses CREATE OR REPLACE FUNCTION
-- -----------------------------------------------------------

CREATE OR REPLACE FUNCTION normalize_price_unit(raw_unit text)
RETURNS jsonb AS $$
DECLARE
    amount numeric := null;
    base text := null;
    modifier text := null;
    period text := null;
    notes text := null;
BEGIN
    -----------------------------------------------------
    -- 1) Extract numeric amount and handle K/M/B multipliers
    -----------------------------------------------------
    IF raw_unit ~ '^[0-9]+' THEN
        amount := regexp_replace(raw_unit, '^([0-9]+).*', '\1')::numeric;
    END IF;

    IF raw_unit ~ '^[0-9]+K' THEN
        amount := amount * 1000;
    ELSIF raw_unit ~ '^[0-9]+M' THEN
        amount := amount * 1000000;
    ELSIF raw_unit ~ '^[0-9]+B' THEN
        amount := amount * 1000000000;
    END IF;

    -----------------------------------------------------
    -- 2) Extract period if present
    -----------------------------------------------------
    IF raw_unit ILIKE '%/hour%' OR raw_unit ILIKE '% hour%' THEN
        period := 'hour';
    ELSIF raw_unit ILIKE '%/minute%' OR raw_unit ILIKE '% minute%' THEN
        period := 'minute';
    ELSIF raw_unit ILIKE '%/second%' OR raw_unit ILIKE '% second%' THEN
        period := 'second';
    ELSIF raw_unit ILIKE '%/month%' OR raw_unit ILIKE '% month%' THEN
        period := 'month';
    ELSIF raw_unit ILIKE '%/day%' OR raw_unit ILIKE '% day%' THEN
        period := 'day';
    ELSIF raw_unit ILIKE '%/year%' OR raw_unit ILIKE '% year%' THEN
        period := 'year';
    END IF;

    -----------------------------------------------------
    -- 3) Extract base unit
    -----------------------------------------------------
    base := regexp_replace(raw_unit, '^[0-9KMB/ ]+', '', 'g');
    base := regexp_replace(base, '(per|/|hour|minute|second|day|month|year).*', '', 'gi');
    base := trim(base);

    -----------------------------------------------------
    -- 4) Handle known composite patterns
    -----------------------------------------------------
    IF raw_unit ILIKE '%GB-Second%' THEN
        base := 'GB';
        period := 'second';
        modifier := regexp_replace(raw_unit, 'GB-Second.*', '', 'i');
        modifier := regexp_replace(modifier, '[- ]$', '', '');
    ELSIF raw_unit ILIKE '%Lambda-GB-Second%' THEN
        base := 'GB';
        period := 'second';
        modifier := 'Lambda';
    ELSIF raw_unit ILIKE '%GB-Hours%' THEN
        base := 'GB';
        period := 'hour';
    ELSIF raw_unit ILIKE '%GiB-Hours%' THEN
        base := 'GiB';
        period := 'hour';
    END IF;

    -----------------------------------------------------
    -- 5) Vendor/region-specific notes
    -----------------------------------------------------
    IF base ILIKE 'APS%' OR base ILIKE 'CAN%' OR base ILIKE 'EUC%' OR base ILIKE 'SAE%' THEN
        notes := raw_unit;
    END IF;

    RETURN jsonb_build_object(
        'amount', amount,
        'base', base,
        'modifier', modifier,
        'period', period,
        'notes', notes
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;
