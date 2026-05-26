-- Building Management — Row-Level Security policies
-- See SPEC.md §4.3, §5
--
-- All tenant-scoped tables get RLS enabled and a tenant_isolation policy
-- that matches against (auth.jwt() ->> 'tenant_id').
--
-- For resident-specific tables, an additional policy restricts to rows
-- linked to apartments the user is currently assigned to.

-- Helper functions to read JWT claims safely
create or replace function current_tenant_id() returns uuid
language sql stable as $$
  select nullif(current_setting('request.jwt.claim.tenant_id', true), '')::uuid;
$$;

create or replace function current_user_role() returns text
language sql stable as $$
  select nullif(current_setting('request.jwt.claim.role', true), '');
$$;

create or replace function current_person_id() returns uuid
language sql stable as $$
  select nullif(current_setting('request.jwt.claim.person_id', true), '')::uuid;
$$;

-- Convenience macro inline below: we enable RLS and create one
-- tenant_isolation policy per table.

-- ---- tenants ----
alter table tenants enable row level security;
create policy tenants_self on tenants for all
  using (id = current_tenant_id()) with check (id = current_tenant_id());

-- ---- buildings ----
alter table buildings enable row level security;
create policy buildings_tenant on buildings for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

-- Resident can only see buildings they have an active assignment to (via apartments)
create policy buildings_resident on buildings for select
  using (
    current_user_role() = 'resident' and exists (
      select 1 from apartment_assignments aa
      join apartments ap on ap.id = aa.apartment_id
      where ap.building_id = buildings.id
        and aa.person_id = current_person_id()
        and aa.status = 'active'
        and (aa.valid_to is null or aa.valid_to >= current_date)
    )
  );

-- ---- apartments ----
alter table apartments enable row level security;
create policy apartments_tenant on apartments for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
create policy apartments_resident on apartments for select
  using (
    current_user_role() = 'resident' and exists (
      select 1 from apartment_assignments aa
      where aa.apartment_id = apartments.id
        and aa.person_id = current_person_id()
        and aa.status = 'active'
    )
  );

-- ---- people ----
alter table people enable row level security;
create policy people_tenant on people for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
create policy people_self on people for select
  using (current_user_role() = 'resident' and id = current_person_id());

-- ---- management_users ----
alter table management_users enable row level security;
create policy management_users_tenant on management_users for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

-- ---- maintenance_workers ----
alter table maintenance_workers enable row level security;
create policy maintenance_workers_tenant on maintenance_workers for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

-- ---- worker_building_assignments ----
alter table worker_building_assignments enable row level security;
create policy worker_building_assignments_tenant on worker_building_assignments for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

-- ---- apartment_assignments ----
alter table apartment_assignments enable row level security;
create policy apartment_assignments_tenant on apartment_assignments for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
create policy apartment_assignments_self on apartment_assignments for select
  using (current_user_role() = 'resident' and person_id = current_person_id());

-- ---- rental_contracts ----
alter table rental_contracts enable row level security;
create policy rental_contracts_tenant on rental_contracts for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
create policy rental_contracts_party on rental_contracts for select
  using (current_user_role() = 'resident' and (
    owner_person_id = current_person_id() or renter_person_id = current_person_id()
  ));

-- ---- charge_schedules ----
alter table charge_schedules enable row level security;
create policy charge_schedules_tenant on charge_schedules for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

-- ---- charges ----
alter table charges enable row level security;
create policy charges_tenant on charges for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
-- Resident sees only charges where they are the billed_to_person, OR
-- they are the owner of the apartment (full visibility).
create policy charges_resident on charges for select
  using (
    current_user_role() = 'resident' and (
      billed_to_person_id = current_person_id() or
      exists (
        select 1 from apartment_assignments aa
        where aa.apartment_id = charges.apartment_id
          and aa.person_id = current_person_id()
          and aa.role = 'owner'
          and aa.status = 'active'
      )
    )
  );

-- ---- payments ----
alter table payments enable row level security;
create policy payments_tenant on payments for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
create policy payments_self on payments for select
  using (current_user_role() = 'resident' and paid_by_person_id = current_person_id());

-- ---- payment_methods ----
alter table payment_methods enable row level security;
create policy payment_methods_tenant on payment_methods for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
create policy payment_methods_owner on payment_methods for all
  using (current_user_role() = 'resident' and owner_person_id = current_person_id())
  with check (current_user_role() = 'resident' and owner_person_id = current_person_id());

-- ---- invoices ----
alter table invoices enable row level security;
create policy invoices_tenant on invoices for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
create policy invoices_customer on invoices for select
  using (current_user_role() = 'resident' and customer_person_id = current_person_id());

alter table invoice_series enable row level security;
create policy invoice_series_tenant on invoice_series for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table invoice_line_items enable row level security;
create policy invoice_line_items_tenant on invoice_line_items for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

-- ---- checks ----
alter table checks enable row level security;
create policy checks_tenant on checks for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
create policy checks_payer on checks for select
  using (current_user_role() = 'resident' and payer_person_id = current_person_id());

alter table check_batches enable row level security;
create policy check_batches_tenant on check_batches for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table bounced_checks enable row level security;
create policy bounced_checks_tenant on bounced_checks for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

-- ---- documents ----
alter table documents enable row level security;
create policy documents_tenant on documents for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table document_versions enable row level security;
create policy document_versions_tenant on document_versions for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table document_acls enable row level security;
create policy document_acls_tenant on document_acls for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

-- ---- tickets ----
alter table service_tickets enable row level security;
create policy service_tickets_tenant on service_tickets for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
create policy service_tickets_resident on service_tickets for select
  using (
    current_user_role() = 'resident' and exists (
      select 1 from apartment_assignments aa
      where aa.apartment_id = service_tickets.apartment_id
        and aa.person_id = current_person_id()
        and aa.status = 'active'
    )
  );

alter table ticket_comments enable row level security;
create policy ticket_comments_tenant on ticket_comments for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

-- ---- tasks ----
alter table tasks enable row level security;
create policy tasks_tenant on tasks for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
create policy tasks_assigned_worker on tasks for select
  using (
    current_user_role() = 'maintenance' and exists (
      select 1 from maintenance_workers mw
      where mw.id = tasks.assigned_worker_id
        and mw.supabase_user_id::text = current_setting('request.jwt.claim.sub', true)
    )
  );

-- ---- communication ----
alter table bulletin_posts enable row level security;
create policy bulletin_posts_tenant on bulletin_posts for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table bulletin_reactions enable row level security;
create policy bulletin_reactions_tenant on bulletin_reactions for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table bulletin_comments enable row level security;
create policy bulletin_comments_tenant on bulletin_comments for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table polls enable row level security;
create policy polls_tenant on polls for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table votes enable row level security;
create policy votes_tenant on votes for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table conversations enable row level security;
create policy conversations_tenant on conversations for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
create policy conversations_self on conversations for select
  using (current_user_role() = 'resident' and person_id = current_person_id());

alter table messages enable row level security;
create policy messages_tenant on messages for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table bot_conversations enable row level security;
create policy bot_conversations_tenant on bot_conversations for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table notifications enable row level security;
create policy notifications_tenant on notifications for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

-- ---- vendors ----
alter table vendors enable row level security;
create policy vendors_tenant on vendors for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table vendor_invoices enable row level security;
create policy vendor_invoices_tenant on vendor_invoices for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table vendor_payouts enable row level security;
create policy vendor_payouts_tenant on vendor_payouts for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

-- ---- addons ----
alter table addon_products enable row level security;
create policy addon_products_tenant on addon_products for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table addon_orders enable row level security;
create policy addon_orders_tenant on addon_orders for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

-- ---- access ----
alter table access_gates enable row level security;
create policy access_gates_tenant on access_gates for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table guest_codes enable row level security;
create policy guest_codes_tenant on guest_codes for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table access_events enable row level security;
create policy access_events_tenant on access_events for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

-- ---- audit + files + invitations + kb ----
alter table audit_log enable row level security;
create policy audit_log_tenant on audit_log for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table files enable row level security;
create policy files_tenant on files for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table invitations enable row level security;
create policy invitations_tenant on invitations for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table kb_documents enable row level security;
create policy kb_documents_tenant on kb_documents for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());

alter table kb_chunks enable row level security;
create policy kb_chunks_tenant on kb_chunks for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
