from unittest.mock import patch, MagicMock
from scheduler import run_pipeline, PIPELINE_STAGES


def test_pipeline_stages_are_in_dependency_order():
    assert PIPELINE_STAGES == [
        "generate_data.py",
        "clean_data.py",
        "calculate_dgca_weights.py",
        "calculate_index.py",
        "backtest_index.py",
        "load_to_database.py",
    ]

def test_run_pipeline_calls_every_stage_in_order():
    with patch("scheduler.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        run_pipeline()
        called_stages = [call.args[0][1] for call in mock_run.call_args_list]
        assert called_stages == PIPELINE_STAGES

def test_run_pipeline_stops_on_first_failure():
    with patch("scheduler.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=1),  # clean_data.py fails
        ]
        run_pipeline()
        assert mock_run.call_count == 2  # never reaches later stages
