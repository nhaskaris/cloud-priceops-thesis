CREATE OR REPLACE FUNCTION classify_domain(
    service_name TEXT,
    instance_type TEXT
)
RETURNS TEXT AS $$
DECLARE
    sn TEXT := LOWER(COALESCE(service_name, '') || '.' || COALESCE(instance_type, ''));
    -- Use this cleaned version for structural matching (db, accelerated, iaas)
    sn_clean TEXT := REPLACE(REPLACE(sn, ' ', ''), '-', ''); 
    
    -- Expanded list of standard sizes, including 'large'
    iaas_sizes TEXT := '(xlarge|xl|[0-9]+xlarge|metal|micro|nano|small|medium|large|flex\.xlarge)';
    
    -- Allowed EC2 Family Prefixes (used for simple starting checks)
    family_prefixes TEXT := '(m|c|r|x|z|u|p|g|inf|f|dl|i|d|t|a|db|hs)';
    
    -- Check if the cleaned string starts with a recognized service category (e.g., generalpurpose.)
    iaas_prefix_match BOOLEAN := 
        sn_clean LIKE 'generalpurpose.%' OR 
        sn_clean LIKE 'computeoptimized.%' OR
        sn_clean LIKE 'storageoptimized.%' OR
        sn_clean LIKE 'stream.compute.%' OR
        sn_clean LIKE 'stream.memory.%' OR
        sn_clean LIKE 'stream.standard.%';
    
    -- Check if the cleaned string starts with a bare family letter (e.g., c1.medium)
    iaas_family_match BOOLEAN := 
        sn_clean ~ ('^' || family_prefixes || '[a-z0-9\.\-]*?' || iaas_sizes || '$') OR
        sn_clean ~ ('^' || family_prefixes || '[a-z0-9\.\-]*?$');

BEGIN
    -- ... (DB and Accelerated rules remain the same, using sn_clean for consistency) ...
    IF sn_clean LIKE 'db.%' OR sn_clean LIKE '%db.%' THEN
        RETURN 'db';
    
    ELSIF sn_clean LIKE '%gpu%' OR sn_clean LIKE '%graphics%' OR sn_clean LIKE '%accelerated%' OR sn_clean LIKE 'stream.graphics%' THEN
        RETURN 'accelerated';
    
    -- 3. IaaS EC2-like instances (New Logic)
    -- This uses the pre-calculated boolean checks for clarity and robustness
    ELSIF iaas_prefix_match OR iaas_family_match
    THEN
        RETURN 'iaas';
    
    -- ... (PaaS, SaaS, and Fallback rules remain the same, using original SN) ...
    ELSIF sn LIKE '%bigquery%' OR sn LIKE '%firestore%' OR sn LIKE '%memorystore%' OR sn LIKE '%cosmos%' OR sn LIKE '%pub/sub%' OR sn LIKE '%timestream%' OR sn LIKE '%kafka%' OR sn LIKE '%redis%' OR sn LIKE '%queue%' OR sn LIKE '%sql%' OR sn LIKE '%lake%' OR sn LIKE '%storage%' OR sn LIKE '%kms%' OR sn LIKE '%secret manager%' OR sn LIKE '%api%' OR sn LIKE '%ml%' OR sn LIKE '%analytics%' OR sn LIKE '%etl%' OR sn LIKE '%data%' OR sn LIKE '%integration%' OR sn LIKE '%search%' THEN
        RETURN 'paas';

    ELSIF sn LIKE '%wordpress%' OR sn LIKE '%drupal%' OR sn LIKE '%prestashop%' OR sn LIKE '%wiki%' OR sn LIKE '%mediawiki%' OR sn LIKE '%portal%' OR sn LIKE '%erp%' OR sn LIKE '%crm%' OR sn LIKE '%cms%' OR sn LIKE '%store%' OR sn LIKE '%gallery%' OR sn LIKE '%ecommerce%' OR sn LIKE '%nextcloud%' OR sn LIKE '%helpdesk%' OR sn LIKE '%forum%' OR sn LIKE '%discourse%' OR sn LIKE '%dolibarr%' OR sn LIKE '%sentrifugo%' OR sn LIKE '%saas%' THEN
        RETURN 'saas';
    
    ELSE
        RETURN 'other';
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;