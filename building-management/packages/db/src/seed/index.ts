/**
 * Seed script — produces the demo tenant described in SPEC.md §4 and §31.
 *
 * Creates:
 *  - 1 tenant
 *  - 2 buildings
 *  - 30 apartments
 *  - 50 people
 *  - 4 rental scenarios (owner-occupant / renter-pays / owner-pays / split)
 *  - 1 monthly charge schedule
 *  - 3 service tickets
 *  - 2 vendors
 *
 * Usage: pnpm --filter @bm/db seed
 *
 * Requires SUPABASE_DB_URL pointing at a freshly-migrated DB.
 */

import { getPool } from '../index';

async function seed() {
  const pool = getPool();
  const client = await pool.connect();
  try {
    console.log('[seed] starting');
    await client.query('begin');

    const tenant = await client.query(
      `insert into tenants (name, legal_name, vat_id, billing_email, plan)
       values ('חברת ניהול דמו בע״מ', 'Demo Management Ltd.', '514000001',
               'demo@example.com', 'pro')
       returning id`,
    );
    const tenantId = tenant.rows[0].id;
    console.log('[seed] tenant', tenantId);

    const building1 = await client.query(
      `insert into buildings (tenant_id, name, address_line, city, postal_code, num_floors, num_apartments)
       values ($1, 'בניין הרצל 10', 'הרצל 10', 'תל אביב', '6577410', 8, 20)
       returning id`,
      [tenantId],
    );
    const building2 = await client.query(
      `insert into buildings (tenant_id, name, address_line, city, postal_code, num_floors, num_apartments)
       values ($1, 'מגדל בן יהודה', 'בן יהודה 100', 'תל אביב', '6343202', 12, 10)
       returning id`,
      [tenantId],
    );

    const b1 = building1.rows[0].id;
    const b2 = building2.rows[0].id;
    console.log('[seed] buildings', b1, b2);

    // Apartments
    const apartments: string[] = [];
    for (let i = 1; i <= 20; i++) {
      const r = await client.query(
        `insert into apartments (tenant_id, building_id, unit_number, floor, size_sqm, num_rooms, monthly_dues_amount)
         values ($1, $2, $3, $4, $5, $6, 350)
         returning id`,
        [tenantId, b1, String(i), Math.ceil(i / 3), 70 + (i % 10) * 5, 3 + (i % 3) * 0.5],
      );
      apartments.push(r.rows[0].id);
    }
    for (let i = 1; i <= 10; i++) {
      const r = await client.query(
        `insert into apartments (tenant_id, building_id, unit_number, floor, size_sqm, num_rooms, monthly_dues_amount)
         values ($1, $2, $3, $4, $5, $6, 450)
         returning id`,
        [tenantId, b2, `${i}A`, i, 90 + i * 3, 4],
      );
      apartments.push(r.rows[0].id);
    }
    console.log('[seed] apartments:', apartments.length);

    // People
    const peopleIds: string[] = [];
    for (let i = 0; i < 50; i++) {
      const name = `דייר ${i + 1}`;
      const phone = `+9725${String(50000000 + i).padStart(8, '0')}`;
      const r = await client.query(
        `insert into people (tenant_id, full_name, phone_e164, email, claim_status)
         values ($1, $2, $3, $4, 'approved')
         returning id`,
        [tenantId, name, phone, `dayar${i + 1}@example.com`],
      );
      peopleIds.push(r.rows[0].id);
    }
    console.log('[seed] people:', peopleIds.length);

    // ---- 4 rental scenarios per SPEC §3.6.7 ----

    // Scenario A: owner-occupant on apartment[0]
    await client.query(
      `insert into apartment_assignments
        (tenant_id, apartment_id, person_id, role, is_primary, is_occupant, is_bill_payer, valid_from, status)
       values ($1, $2, $3, 'owner', true, true, true, current_date, 'active')`,
      [tenantId, apartments[0], peopleIds[0]],
    );
    await client.query(
      `update apartments set occupancy_status = 'owner_occupied' where id = $1`,
      [apartments[0]],
    );

    // Scenario B: renter pays (apartment[1])
    await client.query(
      `insert into rental_contracts
        (tenant_id, apartment_id, owner_person_id, renter_person_id, start_date, vaad_responsibility, status)
       values ($1, $2, $3, $4, current_date - interval '60 days', 'renter_pays', 'active')`,
      [tenantId, apartments[1], peopleIds[1], peopleIds[2]],
    );

    // Scenario C: owner pays for renter (apartment[2])
    await client.query(
      `insert into rental_contracts
        (tenant_id, apartment_id, owner_person_id, renter_person_id, start_date, vaad_responsibility, status)
       values ($1, $2, $3, $4, current_date - interval '30 days', 'owner_pays', 'active')`,
      [tenantId, apartments[2], peopleIds[3], peopleIds[4]],
    );

    // Scenario D: split 50/50 (apartment[3])
    await client.query(
      `insert into rental_contracts
        (tenant_id, apartment_id, owner_person_id, renter_person_id, start_date, vaad_responsibility, split_renter_pct, status)
       values ($1, $2, $3, $4, current_date - interval '90 days', 'split', 50, 'active')`,
      [tenantId, apartments[3], peopleIds[5], peopleIds[6]],
    );

    // Remaining apartments: owner-occupant by default
    for (let i = 4; i < apartments.length && i < 30; i++) {
      await client.query(
        `insert into apartment_assignments
          (tenant_id, apartment_id, person_id, role, is_primary, is_occupant, is_bill_payer, valid_from, status)
         values ($1, $2, $3, 'owner', true, true, true, current_date, 'active')`,
        [tenantId, apartments[i], peopleIds[i + 6]],
      );
      await client.query(
        `update apartments set occupancy_status = 'owner_occupied' where id = $1`,
        [apartments[i]],
      );
    }

    // Charge schedule (monthly ₪350 per apartment for building 1)
    await client.query(
      `insert into charge_schedules
        (tenant_id, building_id, name, amount, cadence, day_of_month, start_date, installments_allowed, bill_payer_rule, status)
       values ($1, $2, 'ועד בית - הרצל 10', 350, 'monthly', 1, current_date - interval '60 days', 6, 'current_bill_payer', 'active')`,
      [tenantId, b1],
    );

    // Invoice series — one tax_invoice_receipt series per tenant
    await client.query(
      `insert into invoice_series (tenant_id, document_type, name, prefix, next_serial)
       values ($1, 'tax_invoice_receipt', 'חשבונית מס/קבלה', 'INV', 1),
              ($1, 'credit_note', 'חשבונית זיכוי', 'CN', 1)`,
      [tenantId],
    );

    // A few sample charges
    for (let i = 0; i < 5; i++) {
      const apt = apartments[i];
      const aa = await client.query(
        `select person_id from apartment_assignments where apartment_id = $1 and is_bill_payer = true and status='active' limit 1`,
        [apt],
      );
      if (aa.rows.length === 0) continue;
      await client.query(
        `insert into charges (tenant_id, building_id, apartment_id, billed_to_person_id, description, amount, due_date)
         values ($1, $2, $3, $4, 'ועד בית - חודש נוכחי', 350, current_date + interval '14 days')`,
        [tenantId, b1, apt, aa.rows[0].person_id],
      );
    }

    // A few sample tickets
    for (let i = 0; i < 3; i++) {
      await client.query(
        `insert into service_tickets
          (tenant_id, building_id, apartment_id, opened_by_person_id, intake_channel, title, description, category, priority)
         values ($1, $2, $3, $4, 'app', $5, $6, $7, $8)`,
        [
          tenantId,
          b1,
          apartments[i],
          peopleIds[i],
          ['נזילה במטבח', 'תאורת המסדרון לא עובדת', 'דלת חדר אשפה'][i],
          ['ישנה נזילה מתחת לכיור', 'נורה לא דולקת', 'נשברה הידית'][i],
          ['plumbing', 'electrical', 'common_area'][i],
          ['high', 'med', 'low'][i],
        ],
      );
    }

    // Vendors
    await client.query(
      `insert into vendors (tenant_id, name, contact_name, phone, services, status)
       values ($1, 'שרברב נחמני', 'נחמני', '+972501111111', $2::jsonb, 'active'),
              ($1, 'חשמלאי ארז', 'ארז', '+972502222222', $3::jsonb, 'active')`,
      [tenantId, JSON.stringify(['plumbing']), JSON.stringify(['electrical'])],
    );

    await client.query('commit');
    console.log('[seed] done.');
  } catch (err) {
    await client.query('rollback');
    console.error('[seed] failed:', err);
    process.exitCode = 1;
  } finally {
    client.release();
    await pool.end();
  }
}

seed().catch((err) => {
  console.error(err);
  process.exit(1);
});
