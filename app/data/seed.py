"""Seed sample procurement data into Neo4j for demo purposes."""

from neo4j import GraphDatabase
from app.config import settings


SEED_CYPHER = """
// Tenants
MERGE (t:Tenant {id: 'tenant-001'}) SET t.name = 'Acme Corp', t.created_at = datetime();

// Suppliers
MERGE (s1:Supplier {id: 'sup-001'}) SET s1 += {name: 'TechFlow Solutions', country: 'USA', industry: 'Technology', tenant_id: 'tenant-001', domain: 'techflow.com', data_confidence: 'high'};
MERGE (s2:Supplier {id: 'sup-002'}) SET s2 += {name: 'GlobalMed Supplies', country: 'Germany', industry: 'Healthcare', tenant_id: 'tenant-001', domain: 'globalmed.de', data_confidence: 'high'};
MERGE (s3:Supplier {id: 'sup-003'}) SET s3 += {name: 'SecureNet Inc', country: 'USA', industry: 'Cybersecurity', tenant_id: 'tenant-001', domain: 'securenet.io', data_confidence: 'medium'};
MERGE (s4:Supplier {id: 'sup-004'}) SET s4 += {name: 'CloudArch Partners', country: 'UK', industry: 'Cloud Services', tenant_id: 'tenant-001', domain: 'cloudarch.co.uk', data_confidence: 'high'};

// Contracts
MERGE (c1:Contract {id: 'ctr-001'}) SET c1 += {title: 'Enterprise Software License', status: 'active', contract_type: 'license', value: 250000.0, currency: 'USD', start_date: '2024-01-01', end_date: '2026-03-15', renewal_date: '2026-01-15', auto_renewal: false, risk_score: 7.5, tenant_id: 'tenant-001'};
MERGE (c2:Contract {id: 'ctr-002'}) SET c2 += {title: 'Medical Device Supply Agreement', status: 'active', contract_type: 'supply', value: 180000.0, currency: 'EUR', start_date: '2023-06-01', end_date: '2026-04-30', renewal_date: '2026-02-28', auto_renewal: true, risk_score: 4.2, tenant_id: 'tenant-001'};
MERGE (c3:Contract {id: 'ctr-003'}) SET c3 += {title: 'Cybersecurity Managed Services', status: 'active', contract_type: 'service', value: 95000.0, currency: 'USD', start_date: '2025-01-01', end_date: '2026-06-30', renewal_date: '2026-04-30', auto_renewal: false, risk_score: 8.9, tenant_id: 'tenant-001'};
MERGE (c4:Contract {id: 'ctr-004'}) SET c4 += {title: 'Cloud Infrastructure SLA', status: 'active', contract_type: 'service', value: 320000.0, currency: 'USD', start_date: '2024-07-01', end_date: '2027-06-30', renewal_date: '2027-04-30', auto_renewal: true, risk_score: 3.1, tenant_id: 'tenant-001'};
MERGE (c5:Contract {id: 'ctr-005'}) SET c5 += {title: 'Legacy Support Contract', status: 'expiring', contract_type: 'support', value: 45000.0, currency: 'USD', start_date: '2022-01-01', end_date: '2026-02-28', renewal_date: '2026-01-01', auto_renewal: false, risk_score: 6.8, tenant_id: 'tenant-001'};

// Contract Lines
MERGE (l1:ContractLine {id: 'line-001'}) SET l1 += {line_number: 1, description: 'Core Platform License', unit_price: 150000.0, quantity_committed: 1.0, uom: 'license', currency: 'USD', category: 'software', tenant_id: 'tenant-001'};
MERGE (l2:ContractLine {id: 'line-002'}) SET l2 += {line_number: 2, description: 'Premium Support', unit_price: 100000.0, quantity_committed: 1.0, uom: 'year', currency: 'USD', category: 'support', tenant_id: 'tenant-001'};

// Contract Obligations
MERGE (o1:ContractObligation {id: 'obl-001'}) SET o1 += {type: 'payment', description: 'Annual license payment due Q1', due_date: '2026-03-01', is_mandatory: true, status: 'pending', tenant_id: 'tenant-001'};
MERGE (o2:ContractObligation {id: 'obl-002'}) SET o2 += {type: 'compliance', description: 'SOC2 audit compliance report submission', due_date: '2026-04-01', is_mandatory: true, status: 'pending', tenant_id: 'tenant-001'};
MERGE (o3:ContractObligation {id: 'obl-003'}) SET o3 += {type: 'notice', description: '90-day termination notice window opens', due_date: '2025-12-15', is_mandatory: true, status: 'overdue', tenant_id: 'tenant-001'};
MERGE (o4:ContractObligation {id: 'obl-004'}) SET o4 += {type: 'review', description: 'Annual security assessment', due_date: '2026-02-01', is_mandatory: false, status: 'pending', tenant_id: 'tenant-001'};

// Invoice
MERGE (inv1:Invoice {id: 'inv-001'}) SET inv1 += {invoice_number: 'INV-2025-001', invoice_date: '2025-01-15', due_date: '2025-02-15', total_amount: 125000.0, subtotal: 113636.36, tax_amount: 11363.64, amount_due: 0.0, currency: 'USD', payment_terms: 'NET30', status: 'paid', contract_id: 'ctr-001', supplier_id: 'sup-001', tenant_id: 'tenant-001'};

// Relationships
MERGE (s1)-[:HAS_CONTRACT]->(c1);
MERGE (s1)-[:HAS_CONTRACT]->(c5);
MERGE (s2)-[:HAS_CONTRACT]->(c2);
MERGE (s3)-[:HAS_CONTRACT]->(c3);
MERGE (s4)-[:HAS_CONTRACT]->(c4);
MERGE (c1)-[:HAS_LINE]->(l1);
MERGE (c1)-[:HAS_LINE]->(l2);
MERGE (c1)-[:HAS_OBLIGATION]->(o1);
MERGE (c1)-[:HAS_OBLIGATION]->(o3);
MERGE (c3)-[:HAS_OBLIGATION]->(o2);
MERGE (c3)-[:HAS_OBLIGATION]->(o4);
MERGE (inv1)-[:RELATES_TO_CONTRACT]->(c1);
"""


def seed_database() -> None:
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    with driver.session() as session:
        for statement in SEED_CYPHER.strip().split(";"):
            statement = statement.strip()
            if statement:
                session.run(statement)
    driver.close()
    print("Seed data loaded successfully.")


if __name__ == "__main__":
    seed_database()
