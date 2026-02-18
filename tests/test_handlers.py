"""Integration tests for bot handlers — direct function calls with mocks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avito_autoload.bot.states import ProjectStates

from conftest import (
    TEST_ADDRESSES,
    TEST_CA_DATA,
    TEST_CATEGORIES_DATA,
    TEST_CHAT_ID,
    TEST_COMPANY_INFO,
    TEST_COMPETITORS_TEXT,
    TEST_MANAGERS,
    TEST_NICHE,
    TEST_PHONE,
    TEST_PRICELIST_TEXT,
    TEST_PROJECT_ID,
    TEST_TEMPLATE_DATA,
    TEST_TITLE_INFO,
    TEST_USER_ID,
    make_callback,
    make_document_message,
    make_message,
    make_state,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# start.py handlers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestStartHandlers:
    async def test_cmd_start(self, test_db):
        from avito_autoload.bot.handlers.start import cmd_start

        msg = make_message("/start")
        state = make_state()

        await cmd_start(msg, state, test_db)

        # Should create project and set state
        assert await state.get_state() == ProjectStates.waiting_niche
        data = await state.get_data()
        assert "project_id" in data
        # Should send 2 messages: welcome + niche question
        assert msg.answer.call_count == 2

    async def test_cmd_help(self):
        from avito_autoload.bot.handlers.start import cmd_help

        msg = make_message("/help")
        await cmd_help(msg)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "/start" in text
        assert "/cancel" in text

    async def test_cmd_cancel(self):
        from avito_autoload.bot.handlers.start import cmd_cancel

        msg = make_message("/cancel")
        state = make_state(
            current_state=ProjectStates.waiting_pricelist.state,
            data={"project_id": 1},
        )

        await cmd_cancel(msg, state)

        assert await state.get_state() is None
        msg.answer.assert_called_once()

    async def test_cmd_status(self, test_db):
        from avito_autoload.bot.handlers.start import cmd_status

        # Create a project first
        pid = await test_db.create_project(TEST_USER_ID)
        await test_db.update_project(pid, niche=TEST_NICHE)

        msg = make_message("/status")
        state = make_state(current_state=ProjectStates.waiting_pricelist.state)

        await cmd_status(msg, state, test_db)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert TEST_NICHE in text

    async def test_cmd_status_no_project(self, test_db):
        from avito_autoload.bot.handlers.start import cmd_status

        msg = make_message("/status", user_id=99999)
        state = make_state()

        await cmd_status(msg, state, test_db)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "/start" in text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# collect.py handlers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCollectHandlers:
    async def test_receive_niche(self, test_db):
        from avito_autoload.bot.handlers.collect import receive_niche

        pid = await test_db.create_project(TEST_USER_ID)
        msg = make_message(TEST_NICHE)
        state = make_state(data={"project_id": pid})

        await receive_niche(msg, state, test_db)

        assert await state.get_state() == ProjectStates.waiting_pricelist
        # Should send 2 messages: confirmation + pricelist question
        assert msg.answer.call_count == 2

        # Verify DB
        project = await test_db.get_active_project(TEST_USER_ID)
        assert project["niche"] == TEST_NICHE

    async def test_receive_pricelist_text(self, test_db):
        from avito_autoload.bot.handlers.collect import receive_pricelist_text

        pid = await test_db.create_project(TEST_USER_ID)
        msg = make_message(TEST_PRICELIST_TEXT)
        state = make_state(data={"project_id": pid})

        await receive_pricelist_text(msg, state, test_db)

        assert await state.get_state() == ProjectStates.waiting_competitors
        project = await test_db.get_active_project(TEST_USER_ID)
        assert project["pricelist_text"] == TEST_PRICELIST_TEXT

    async def test_receive_pricelist_xlsx(self, test_db, test_file_storage, mock_bot):
        from avito_autoload.bot.handlers.collect import receive_pricelist

        pid = await test_db.create_project(TEST_USER_ID)
        msg = make_document_message("pricelist.xlsx")
        state = make_state(data={"project_id": pid})

        with patch("avito_autoload.parsers.xlsx_parser.parse_xlsx", side_effect=Exception("no file")):
            await receive_pricelist(msg, state, mock_bot, test_db, test_file_storage)

        assert await state.get_state() == ProjectStates.waiting_competitors

    async def test_receive_pricelist_wrong_format(self, test_db, test_file_storage, mock_bot):
        from avito_autoload.bot.handlers.collect import receive_pricelist

        pid = await test_db.create_project(TEST_USER_ID)
        msg = make_document_message("data.csv")  # Wrong format
        state = make_state(data={"project_id": pid})

        await receive_pricelist(msg, state, mock_bot, test_db, test_file_storage)

        # State should NOT change — remains None (no set_state called)
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert ".xlsx" in text

    async def test_receive_competitors_text(self, test_db):
        from avito_autoload.bot.handlers.collect import receive_competitors_text

        pid = await test_db.create_project(TEST_USER_ID)
        msg = make_message(TEST_COMPETITORS_TEXT)
        state = make_state(data={"project_id": pid})

        await receive_competitors_text(msg, state, test_db)

        assert await state.get_state() == ProjectStates.waiting_addresses
        project = await test_db.get_active_project(TEST_USER_ID)
        assert project["competitors_text"] == TEST_COMPETITORS_TEXT

    async def test_receive_addresses(self, test_db):
        from avito_autoload.bot.handlers.collect import receive_addresses

        pid = await test_db.create_project(TEST_USER_ID)
        msg = make_message(TEST_ADDRESSES)
        state = make_state(data={"project_id": pid})

        await receive_addresses(msg, state, test_db)

        assert await state.get_state() == ProjectStates.waiting_managers
        project = await test_db.get_active_project(TEST_USER_ID)
        assert project["addresses"] == TEST_ADDRESSES

    async def test_waiting_addresses_wrong(self):
        from avito_autoload.bot.handlers.collect import waiting_addresses_wrong

        msg = make_message()
        msg.document = MagicMock()  # Sent a file instead of text

        await waiting_addresses_wrong(msg)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "адрес" in text.lower()

    async def test_receive_managers(self, test_db):
        from avito_autoload.bot.handlers.collect import receive_managers

        pid = await test_db.create_project(TEST_USER_ID)
        msg = make_message(TEST_MANAGERS)
        state = make_state(data={"project_id": pid})

        await receive_managers(msg, state, test_db)

        assert await state.get_state() == ProjectStates.waiting_phone
        project = await test_db.get_active_project(TEST_USER_ID)
        assert project["managers"] == TEST_MANAGERS

    async def test_receive_phone(self, test_db):
        from avito_autoload.bot.handlers.collect import receive_phone

        pid = await test_db.create_project(TEST_USER_ID)
        msg = make_message(TEST_PHONE)
        state = make_state(data={"project_id": pid})

        await receive_phone(msg, state, test_db)

        assert await state.get_state() == ProjectStates.waiting_company_info
        project = await test_db.get_active_project(TEST_USER_ID)
        assert project["phone"] == TEST_PHONE

    async def test_receive_company_info(self, test_db):
        from avito_autoload.bot.handlers.collect import receive_company_info

        pid = await test_db.create_project(TEST_USER_ID)
        msg = make_message(TEST_COMPANY_INFO)
        state = make_state(data={"project_id": pid})

        await receive_company_info(msg, state, test_db)

        assert await state.get_state() == ProjectStates.waiting_title_info
        project = await test_db.get_active_project(TEST_USER_ID)
        assert project["company_info"] == TEST_COMPANY_INFO
        # Should send 2 messages: confirmation + title info question
        assert msg.answer.call_count == 2

    async def test_receive_title_info(self, test_db):
        from avito_autoload.bot.handlers.collect import receive_title_info

        pid = await test_db.create_project(TEST_USER_ID)
        msg = make_message(TEST_TITLE_INFO)
        state = make_state(data={"project_id": pid})

        await receive_title_info(msg, state, test_db)

        assert await state.get_state() == ProjectStates.confirming_plan
        project = await test_db.get_active_project(TEST_USER_ID)
        assert project["title_info"] == TEST_TITLE_INFO
        # Should send 3 messages: confirmation + "all data received" + plan
        assert msg.answer.call_count == 3

    async def test_waiting_niche_wrong(self):
        from avito_autoload.bot.handlers.collect import waiting_niche_wrong

        msg = make_message()
        await waiting_niche_wrong(msg)
        msg.answer.assert_called_once()

    async def test_waiting_phone_wrong(self):
        from avito_autoload.bot.handlers.collect import waiting_phone_wrong

        msg = make_message()
        await waiting_phone_wrong(msg)
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "телефон" in text.lower()

    async def test_waiting_managers_wrong(self):
        from avito_autoload.bot.handlers.collect import waiting_managers_wrong

        msg = make_message()
        await waiting_managers_wrong(msg)
        msg.answer.assert_called_once()

    async def test_waiting_company_info_wrong(self):
        from avito_autoload.bot.handlers.collect import waiting_company_info_wrong

        msg = make_message()
        await waiting_company_info_wrong(msg)
        msg.answer.assert_called_once()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# callbacks.py handlers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCallbackHandlers:
    @patch("avito_autoload.bot.handlers.analysis.run_ca_analysis", new_callable=AsyncMock)
    async def test_on_plan_start(self, mock_run_ca, test_db):
        from avito_autoload.bot.handlers.callbacks import on_plan_start

        cb = make_callback("plan_start")
        state = make_state(data={"project_id": 1})

        await on_plan_start(cb, state, test_db)

        cb.answer.assert_called_once()
        assert await state.get_state() == ProjectStates.running_ca_analysis

    @patch("avito_autoload.bot.handlers.analysis.run_template_generation", new_callable=AsyncMock)
    async def test_on_confirm_ca(self, mock_run_template, test_db, test_file_storage):
        from avito_autoload.bot.handlers.callbacks import on_confirm

        cb = make_callback("confirm")
        state = make_state(
            current_state=ProjectStates.confirming_ca.state,
            data={"project_id": 1},
        )

        await on_confirm(cb, state, test_db, test_file_storage)

        assert await state.get_state() == ProjectStates.running_template

    @patch("avito_autoload.bot.handlers.analysis.run_categorization", new_callable=AsyncMock)
    async def test_on_confirm_template(self, mock_run_cat, test_db, test_file_storage):
        from avito_autoload.bot.handlers.callbacks import on_confirm

        cb = make_callback("confirm")
        state = make_state(
            current_state=ProjectStates.confirming_template.state,
            data={"project_id": 1},
        )

        await on_confirm(cb, state, test_db, test_file_storage)

        assert await state.get_state() == ProjectStates.running_categories

    @patch("avito_autoload.bot.handlers.analysis.run_pipeline", new_callable=AsyncMock)
    async def test_on_confirm_categories(self, mock_run_pipe, test_db, test_file_storage):
        from avito_autoload.bot.handlers.callbacks import on_confirm

        cb = make_callback("confirm")
        state = make_state(
            current_state=ProjectStates.confirming_categories.state,
            data={"project_id": 1},
        )

        await on_confirm(cb, state, test_db, test_file_storage)

        assert await state.get_state() == ProjectStates.running_pipeline

    async def test_on_edit_ca(self):
        from avito_autoload.bot.handlers.callbacks import on_edit

        cb = make_callback("edit")
        state = make_state(current_state=ProjectStates.confirming_ca.state)

        await on_edit(cb, state)

        assert await state.get_state() == ProjectStates.editing_ca

    async def test_on_edit_template(self):
        from avito_autoload.bot.handlers.callbacks import on_edit

        cb = make_callback("edit")
        state = make_state(current_state=ProjectStates.confirming_template.state)

        await on_edit(cb, state)

        assert await state.get_state() == ProjectStates.editing_template

    async def test_on_new_project(self):
        from avito_autoload.bot.handlers.callbacks import on_new_project

        cb = make_callback("new_project")
        state = make_state(
            current_state=ProjectStates.complete.state,
            data={"project_id": 1},
        )

        await on_new_project(cb, state)

        assert await state.get_state() is None
        cb.message.answer.assert_called_once()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# analysis.py handlers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAnalysisHandlers:
    @patch("avito_autoload.bot.utils.pdf.markdown_to_pdf", return_value=b"%PDF-fake")
    @patch("avito_autoload.bot.services.ca_analyzer.analyze_target_audience", new_callable=AsyncMock)
    @patch("avito_autoload.bot.services.ca_analyzer.format_ca_summary", return_value="CA Summary")
    async def test_run_ca_analysis(self, mock_format, mock_analyze, mock_pdf, test_db):
        from avito_autoload.bot.handlers.analysis import run_ca_analysis

        mock_analyze.return_value = TEST_CA_DATA

        pid = await test_db.create_project(TEST_USER_ID)
        await test_db.update_project(pid, niche=TEST_NICHE)

        msg = make_message()
        state = make_state(data={"project_id": pid})

        await run_ca_analysis(msg, state, test_db)

        assert await state.get_state() == ProjectStates.confirming_ca
        # Should send: progress + summary + PDF
        assert msg.answer.call_count >= 2
        assert msg.answer_document.call_count == 1

    @patch("avito_autoload.bot.utils.pdf.markdown_to_pdf", return_value=b"%PDF-fake")
    @patch("avito_autoload.bot.services.template_builder.build_template", new_callable=AsyncMock)
    @patch("avito_autoload.bot.services.template_builder.format_template_summary", return_value="Template Summary")
    async def test_run_template_generation(self, mock_format, mock_build, mock_pdf, test_db):
        from avito_autoload.bot.handlers.analysis import run_template_generation

        mock_build.return_value = TEST_TEMPLATE_DATA

        pid = await test_db.create_project(TEST_USER_ID)
        await test_db.update_project(pid, niche=TEST_NICHE)

        msg = make_message()
        state = make_state(data={
            "project_id": pid,
            "niche": TEST_NICHE,
            "ca_data": TEST_CA_DATA,
        })

        await run_template_generation(msg, state, test_db)

        assert await state.get_state() == ProjectStates.confirming_template

    @patch("avito_autoload.bot.utils.pdf.markdown_to_pdf", return_value=b"%PDF-fake")
    @patch("avito_autoload.bot.services.category_fetcher.fetch_categories_for_niche", new_callable=AsyncMock)
    @patch("avito_autoload.bot.services.category_fetcher.format_categories_summary", return_value="Categories")
    async def test_run_categorization(self, mock_format, mock_fetch, mock_pdf, test_db, test_file_storage):
        from avito_autoload.bot.handlers.analysis import run_categorization

        mock_fetch.return_value = TEST_CATEGORIES_DATA

        pid = await test_db.create_project(TEST_USER_ID)
        await test_db.update_project(pid, niche=TEST_NICHE)

        msg = make_message()
        state = make_state(data={"project_id": pid, "niche": TEST_NICHE})

        await run_categorization(msg, state, test_db, test_file_storage)

        assert await state.get_state() == ProjectStates.confirming_categories

    @patch("avito_autoload.bot.utils.pdf.markdown_to_pdf", return_value=b"%PDF-fake")
    @patch("avito_autoload.bot.services.ca_analyzer.analyze_target_audience", new_callable=AsyncMock)
    @patch("avito_autoload.bot.services.ca_analyzer.format_ca_summary", return_value="Updated CA")
    async def test_handle_ca_edit(self, mock_format, mock_analyze, mock_pdf, test_db):
        from avito_autoload.bot.handlers.analysis import handle_ca_edit

        mock_analyze.return_value = TEST_CA_DATA

        pid = await test_db.create_project(TEST_USER_ID)
        await test_db.update_project(pid, niche=TEST_NICHE)

        msg = make_message("Добавь сегмент оптовиков")
        state = make_state(data={"project_id": pid, "niche": TEST_NICHE})

        await handle_ca_edit(msg, state, test_db)

        assert await state.get_state() == ProjectStates.confirming_ca
        # The niche passed to analyze should include corrections
        call_args = mock_analyze.call_args[0][0]
        assert "Добавь сегмент оптовиков" in call_args
