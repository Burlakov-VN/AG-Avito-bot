"""End-to-end conversation flow test: /start through all 8 questions to plan."""

from unittest.mock import AsyncMock, patch

import pytest

from avito_autoload.bot.states import ProjectStates

from conftest import (
    TEST_ADDRESSES,
    TEST_CA_DATA,
    TEST_CATEGORIES_DATA,
    TEST_COMPANY_INFO,
    TEST_COMPETITORS_TEXT,
    TEST_MANAGERS,
    TEST_NICHE,
    TEST_PHONE,
    TEST_PRICELIST_TEXT,
    TEST_TEMPLATE_DATA,
    TEST_TITLE_INFO,
    TEST_USER_ID,
    make_callback,
    make_message,
    make_state,
)


class TestFullConversationFlow:
    """Simulate a complete user conversation from /start to plan confirmation."""

    async def test_data_collection_flow(self, test_db):
        """Test all 8 questions in sequence with correct state transitions."""
        from avito_autoload.bot.handlers.start import cmd_start
        from avito_autoload.bot.handlers.collect import (
            receive_niche,
            receive_pricelist_text,
            receive_competitors_text,
            receive_addresses,
            receive_managers,
            receive_phone,
            receive_company_info,
            receive_title_info,
        )

        state = make_state()

        # Step 1: /start
        msg = make_message("/start")
        await cmd_start(msg, state, test_db)
        assert await state.get_state() == ProjectStates.waiting_niche
        data = await state.get_data()
        project_id = data["project_id"]

        # Step 2: Niche
        msg = make_message(TEST_NICHE)
        await receive_niche(msg, state, test_db)
        assert await state.get_state() == ProjectStates.waiting_pricelist

        # Step 3: Pricelist (text)
        msg = make_message(TEST_PRICELIST_TEXT)
        await receive_pricelist_text(msg, state, test_db)
        assert await state.get_state() == ProjectStates.waiting_competitors

        # Step 4: Competitors (text)
        msg = make_message(TEST_COMPETITORS_TEXT)
        await receive_competitors_text(msg, state, test_db)
        assert await state.get_state() == ProjectStates.waiting_addresses

        # Step 5: Addresses
        msg = make_message(TEST_ADDRESSES)
        await receive_addresses(msg, state, test_db)
        assert await state.get_state() == ProjectStates.waiting_managers

        # Step 6: Managers
        msg = make_message(TEST_MANAGERS)
        await receive_managers(msg, state, test_db)
        assert await state.get_state() == ProjectStates.waiting_phone

        # Step 7: Phone
        msg = make_message(TEST_PHONE)
        await receive_phone(msg, state, test_db)
        assert await state.get_state() == ProjectStates.waiting_company_info

        # Step 8: Company info
        msg = make_message(TEST_COMPANY_INFO)
        await receive_company_info(msg, state, test_db)
        assert await state.get_state() == ProjectStates.waiting_title_info

        # Step 9: Title info
        msg = make_message(TEST_TITLE_INFO)
        await receive_title_info(msg, state, test_db)
        assert await state.get_state() == ProjectStates.confirming_plan

        # Verify all data saved in DB
        project = await test_db.get_active_project(TEST_USER_ID)
        assert project is not None
        assert project["niche"] == TEST_NICHE
        assert project["pricelist_text"] == TEST_PRICELIST_TEXT
        assert project["competitors_text"] == TEST_COMPETITORS_TEXT
        assert project["addresses"] == TEST_ADDRESSES
        assert project["managers"] == TEST_MANAGERS
        assert project["phone"] == TEST_PHONE
        assert project["company_info"] == TEST_COMPANY_INFO
        assert project["title_info"] == TEST_TITLE_INFO

    @patch("avito_autoload.bot.utils.pdf.markdown_to_pdf", return_value=b"%PDF-fake")
    @patch("avito_autoload.bot.services.ca_analyzer.analyze_target_audience", new_callable=AsyncMock)
    @patch("avito_autoload.bot.services.ca_analyzer.format_ca_summary", return_value="CA OK")
    @patch("avito_autoload.bot.services.template_builder.build_template", new_callable=AsyncMock)
    @patch("avito_autoload.bot.services.template_builder.format_template_summary", return_value="TPL OK")
    @patch("avito_autoload.bot.services.category_fetcher.fetch_categories_for_niche", new_callable=AsyncMock)
    @patch("avito_autoload.bot.services.category_fetcher.format_categories_summary", return_value="CAT OK")
    async def test_analysis_stages_flow(
        self,
        mock_cat_fmt,
        mock_cat_fetch,
        mock_tpl_fmt,
        mock_tpl_build,
        mock_ca_fmt,
        mock_ca_analyze,
        mock_pdf,
        test_db,
        test_file_storage,
    ):
        """Test plan_start → CA → template → categories flow."""
        from avito_autoload.bot.handlers.analysis import (
            run_ca_analysis,
            run_categorization,
            run_template_generation,
        )

        mock_ca_analyze.return_value = TEST_CA_DATA
        mock_tpl_build.return_value = TEST_TEMPLATE_DATA
        mock_cat_fetch.return_value = TEST_CATEGORIES_DATA

        pid = await test_db.create_project(TEST_USER_ID)
        await test_db.update_project(pid, niche=TEST_NICHE)

        state = make_state(data={
            "project_id": pid,
            "niche": TEST_NICHE,
        })

        # Stage 1: CA analysis
        msg = make_message()
        await run_ca_analysis(msg, state, test_db)
        assert await state.get_state() == ProjectStates.confirming_ca

        # Stage 2: Template generation
        msg = make_message()
        await run_template_generation(msg, state, test_db)
        assert await state.get_state() == ProjectStates.confirming_template

        # Stage 3: Categorization
        msg = make_message()
        await run_categorization(msg, state, test_db, test_file_storage)
        assert await state.get_state() == ProjectStates.confirming_categories

    async def test_state_order_integrity(self):
        """Verify the expected order of FSM states."""
        expected_collection_order = [
            ProjectStates.waiting_niche,
            ProjectStates.waiting_pricelist,
            ProjectStates.waiting_competitors,
            ProjectStates.waiting_addresses,
            ProjectStates.waiting_managers,
            ProjectStates.waiting_phone,
            ProjectStates.waiting_company_info,
            ProjectStates.waiting_title_info,
            ProjectStates.confirming_plan,
        ]
        # Verify all states exist and are distinct
        state_values = [s.state for s in expected_collection_order]
        assert len(state_values) == len(set(state_values)), "Duplicate states found"

        expected_analysis_order = [
            ProjectStates.running_ca_analysis,
            ProjectStates.confirming_ca,
            ProjectStates.running_template,
            ProjectStates.confirming_template,
            ProjectStates.running_categories,
            ProjectStates.confirming_categories,
            ProjectStates.running_pipeline,
            ProjectStates.complete,
        ]
        state_values = [s.state for s in expected_analysis_order]
        assert len(state_values) == len(set(state_values)), "Duplicate states found"
