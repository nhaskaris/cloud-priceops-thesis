CREATE OR REPLACE FUNCTION classify_domain(
    service_name TEXT,
    instance_type TEXT
)
RETURNS TEXT AS $$
DECLARE
    -- Standardize names for matching
    s_name TEXT := COALESCE(service_name, '');
    sn TEXT := LOWER(s_name || '.' || COALESCE(instance_type, ''));
    sn_clean TEXT := REPLACE(REPLACE(sn, ' ', ''), '-', ''); 
    
    -- IaaS Regex Patterns (Standard Virtual Machines)
    iaas_sizes TEXT := '(xlarge|xl|[0-9]+xlarge|metal|micro|nano|small|medium|large|flex\.xlarge)';
    family_prefixes TEXT := '(m|c|r|x|z|u|p|g|inf|f|dl|i|d|t|a|db|hs)';
    
    iaas_prefix_match BOOLEAN := 
        sn_clean LIKE 'generalpurpose.%' OR 
        sn_clean LIKE 'computeoptimized.%' OR
        sn_clean LIKE 'storageoptimized.%' OR 
        sn_clean LIKE 'stream.compute.%' OR 
        sn_clean LIKE 'stream.memory.%' OR 
        sn_clean LIKE 'stream.standard.%';
    
    iaas_family_match BOOLEAN := 
        sn_clean ~ ('^' || family_prefixes || '[a-z0-9\.\-]*?' || iaas_sizes || '$') OR
        sn_clean ~ ('^' || family_prefixes || '[a-z0-9\.\-]*?$');

BEGIN
    -- 1. FAAS (Function-as-a-Service / Serverless Execution)
    IF s_name IN (
        'AWSLambda', 'Azure Functions', 'Functions', 'Cloud Functions', 
        'Automation', 'Azure Automation', 'Logic Apps', 'AWSEvents', 'Event Grid'
    ) THEN
        RETURN 'faas';

    -- 2. DAAS (Desktop-as-a-Service / Managed User Environments)
    ELSIF s_name IN (
        'Amazon WorkSpaces', 'AmazonAppStream', 'Microsoft Dev Box', 
        'Windows Virtual Desktop', 'AmazonChime'
    ) THEN
        RETURN 'daas';

    -- 3. MANAGED DATABASES (Managed storage engines)
    ELSIF s_name IN (
        'AmazonRDS', 'AmazonDocDB', 'AmazonDynamoDB', 'SQL Database', 
        'SQL Managed Instance', 'Azure Cosmos DB', 'Azure Database for MariaDB', 
        'Azure Database for MySQL', 'Azure Database for PostgreSQL', 'MySQL Database on Azure',
        'Azure Database Migration Service', 'AWSDatabaseMigrationSvc', 'SQL Server Stretch Database'
    ) OR sn_clean LIKE 'db.%' THEN
        RETURN 'db';

    -- 4. EXPLICIT PAAS (High-Level Managed Services / "Platform" layer)
    ELSIF s_name IN (
        -- AI, ML & Intelligence
        'Azure Machine Learning', 'Machine Learning Studio', 'Azure Cognitive Search', 
        'Cognitive Services', 'AmazonSageMaker', 'Azure Applied AI Services', 'AmazonBedrock', 
        'AmazonBedrockAgentCore', 'AmazonBedrockService', 'Intelligent Recommendations', 
        'Azure Bot Service', 'AmazonA2I', 'Microsoft Copilot Studio', 'AI Ops',
        
        -- Analytics, Big Data & Integration
        'Microsoft Fabric', 'Data Lake Analytics', 'Azure Synapse Analytics', 'SQL Data Warehouse',
        'Dataproc', 'AmazonRedshift', 'Azure Data Explorer', 'Azure Databricks', 'AWSGlue', 
        'AWSLakeFormation', 'Stream Analytics', 'Azure Data Factory', 'Azure Data Factory v2',
        'Cloud Dataflow', 'AmazonCloudSearch', 'Time Series Insights', 'HDInsight', 'ElasticMapReduce',
        
        -- Containers & App Platforms
        'Azure Kubernetes Service', 'Azure Container Apps', 'Container Instances', 
        'Azure App Service', 'Azure Spring Cloud', 'Cloud Services', 'Azure Fluid Relay',
        'Container Registry',
        
        -- Security, Identity & Management
        'Microsoft Defender for Cloud', 'Security Center', 'Sentinel', 'Microsoft Purview', 
        'Azure Monitor', 'Log Analytics', 'Insight and Analytics', 'Application Insights',
        'Key Vault', 'Microsoft Entra Domain Services', 'AmazonCognito', 'AmazonDevOpsGuru',
        'AWSFMS', 'AmazonCloudWatch', 'AmazonCloudDirectory', 'AWSIAMAccessAnalyzer',
        'Azure IoT Security', 'App Configuration', 'Azure API Center', 'awskms', 'ACM', 'Backup',
        
        -- Messaging, IoT & Networking PaaS
        'IoT Hub', 'AWSIoT', 'AWSIoTThingsGraph', 'Service Bus', 'Event Hubs', 'Notification Hubs', 
        'Messaging', 'Web PubSub', 'API Management', 'AmazonApiGateway', 'ExpressRoute',
        'Traffic Manager', 'Azure Route Server', 'Azure Front Door Service', 'Content Delivery Network',
        'AmazonCloudFront', 'AWSGlobalAccelerator', 'VPN Gateway', 'Virtual WAN', 'Application Gateway',
        'Azure Bastion', 'Azure API for FHIR', 'Azure Site Recovery', 'Azure Blockchain',
        'Microsoft Graph Services', 'Azure Maps', 'Mixed Reality',
        
        -- Media & Communication APIs
        'AWSElementalMediaLive', 'AWSElementalMediaStore', 'AWSElementalMediaTailor', 
        'Media Services', 'AmazonChimeServices', 'AmazonChimeBusinessCalling', 'AmazonChimeFeatures',
        'AmazonChimeDialin', 'AmazonChimeCallMeAMCS', 'AmazonChimeVoiceConnector', 
        'AmazonChimeDialInAMCS', 'AmazonChimeCallMe'
    ) THEN
        RETURN 'paas';
        
    -- 5. SAAS (High-level Software / Marketplace Solutions)
    ELSIF s_name IN (
        'GitHub AE', 'Power BI', 'Syntex', 'Collibra Data Intelligence Cloud',
        'Inpher, Inc. XOR Secret Computing Platform', 'Fivetran Data Pipelines',
        'Atos - Dev Identity as a Service', 'Blue Medora BindPlane', 'Inpher',
        'HYCU, Inc HYCU', 'AlexaTopSites'
    ) OR sn LIKE '%saas%' THEN
        RETURN 'saas';
    
    -- 6. LICENSES & MARKETPLACE (Specific software surcharges)
    ELSIF s_name IN (
        'Virtual Machines Licenses', 'Check Point Software Technologies CloudGuard', 
        'CrushFTP on Windows 2016', 'CIS Debian Linux 10 Benchmark - Level 1',
        'CIS Red Hat Enterprise Linux 8 Benchmark - Level 1', 
        'CIS Red Hat Enterprise Linux 7 Benchmark - Level 1',
        'CIS Ubuntu Linux 20.04 LTS STIG Benchmark'
    ) THEN
        RETURN 'license';

    -- 7. ACCELERATED (GPU, ASIC, or Specialized Rendering)
    ELSIF sn_clean LIKE '%gpu%' OR sn_clean LIKE '%graphics%' OR sn_clean LIKE '%accelerated%' 
       OR s_name = 'AmazonDeadline' THEN
        RETURN 'accelerated';
    
    -- 8. IAAS (Baseline Infrastructure / Hardware)
    ELSIF iaas_prefix_match OR iaas_family_match OR s_name IN (
        'Virtual Machines', 'Compute Engine', 'AmazonEC2', 'Storage', 
        'Virtual Network', 'Azure Stack Hub', 'Azure Stack Edge', 'Data Box', 
        'Specialized Compute', 'Packet Core', 'HPC Cache', 'Azure NetApp Files',
        'Data Lake Store'
    ) THEN
        RETURN 'iaas';
    
    -- 9. MISC UTILITY (Variable connectivity/usage fees)
    ELSIF s_name IN (
        'Bandwidth', 'AWSDataTransfer', 'Voice', 'SMS', 'Phone Numbers', 
        'Email', 'AWSEndUserMessaging3pFees', 'Network Traversal', 'ContactCenterTelecomm'
    ) THEN
        RETURN 'utility';

    ELSE
        RETURN 'other';
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;