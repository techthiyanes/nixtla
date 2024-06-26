# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/distributed.nixtla_client.ipynb.

# %% auto 0
__all__ = []

# %% ../../nbs/distributed.nixtla_client.ipynb 2
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import fugue
import fugue.api as fa
from fugue import transform, DataFrame, FugueWorkflow, ExecutionEngine
from fugue.collections.yielded import Yielded
from fugue.constants import FUGUE_CONF_WORKFLOW_EXCEPTION_INJECT
from fugue.execution.factory import make_execution_engine
from triad import Schema

# %% ../../nbs/distributed.nixtla_client.ipynb 3
def _cotransform(
    df1: Any,
    df2: Any,
    using: Any,
    schema: Any = None,
    params: Any = None,
    partition: Any = None,
    engine: Any = None,
    engine_conf: Any = None,
    force_output_fugue_dataframe: bool = False,
    as_local: bool = False,
) -> Any:
    dag = FugueWorkflow(compile_conf={FUGUE_CONF_WORKFLOW_EXCEPTION_INJECT: 0})

    src = dag.create_data(df1).zip(dag.create_data(df2), partition=partition)
    tdf = src.transform(
        using=using,
        schema=schema,
        params=params,
        pre_partition=partition,
    )
    tdf.yield_dataframe_as("result", as_local=as_local)
    dag.run(engine, conf=engine_conf)
    result = dag.yields["result"].result  # type:ignore
    if force_output_fugue_dataframe or isinstance(df1, (DataFrame, Yielded)):
        return result
    return result.as_pandas() if result.is_local else result.native  # type:ignore

# %% ../../nbs/distributed.nixtla_client.ipynb 4
class _DistributedNixtlaClient:

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 6,
        retry_interval: int = 10,
        max_wait_time: int = 60,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        self.max_wait_time = max_wait_time

    def _distribute_method(
        self,
        method: Callable,
        df: fugue.AnyDataFrame,
        kwargs: dict,
        schema: str,
        num_partitions: int,
        id_col: str,
        X_df: Optional[fugue.AnyDataFrame] = None,
    ):
        if id_col not in fa.get_column_names(df):
            raise Exception(
                "Distributed environment is meant to forecasts "
                "multiple time series at once. You did not provide "
                "an identifier for each time series."
            )
        engine = make_execution_engine(infer_by=[df])
        if num_partitions is None:
            num_partitions = engine.get_current_parallelism()
        partition = dict(by=id_col, num=num_partitions, algo="coarse")
        params = dict(
            kwargs={**kwargs, "num_partitions": 1},
        )  # local num_partitions
        if X_df is not None:
            # check same engine
            engine_x = make_execution_engine(infer_by=[X_df])
            if repr(engine) != repr(engine_x):
                raise Exception(
                    "Target variable and exogenous variables "
                    "have different engines. Please provide the same "
                    "distributed engine for both inputs."
                )
            result_df = _cotransform(
                df,
                X_df,
                method,
                params=params,
                schema=schema,
                partition=partition,
                engine=engine,
            )
        else:
            result_df = fa.transform(
                df,
                method,
                params=params,
                schema=schema,
                engine=engine,
                partition=partition,
                as_fugue=True,
            )
        return fa.get_native_as_df(result_df)

    def forecast(
        self,
        df: fugue.AnyDataFrame,
        h: int,
        freq: Optional[str] = None,
        id_col: str = "unique_id",
        time_col: str = "ds",
        target_col: str = "y",
        X_df: Optional[fugue.AnyDataFrame] = None,
        level: Optional[List[Union[int, float]]] = None,
        quantiles: Optional[List[float]] = None,
        finetune_steps: int = 0,
        finetune_loss: str = "default",
        clean_ex_first: bool = True,
        validate_api_key: bool = False,
        add_history: bool = False,
        date_features: Union[bool, List[str]] = False,
        date_features_to_one_hot: Union[bool, List[str]] = True,
        model: str = "timegpt-1",
        num_partitions: Optional[int] = None,
    ) -> fugue.AnyDataFrame:
        kwargs = dict(
            h=h,
            freq=freq,
            id_col=id_col,
            time_col=time_col,
            target_col=target_col,
            level=level,
            quantiles=quantiles,
            finetune_steps=finetune_steps,
            finetune_loss=finetune_loss,
            clean_ex_first=clean_ex_first,
            validate_api_key=validate_api_key,
            add_history=add_history,
            date_features=date_features,
            date_features_to_one_hot=date_features_to_one_hot,
            model=model,
        )
        schema = self._get_forecast_schema(
            id_col=id_col,
            time_col=time_col,
            level=level,
            quantiles=quantiles,
        )
        fcst_df = self._distribute_method(
            method=self._forecast if X_df is None else self._forecast_x,
            df=df,
            kwargs=kwargs,
            schema=schema,
            num_partitions=num_partitions,
            id_col=id_col,
            X_df=X_df,
        )
        return fcst_df

    def detect_anomalies(
        self,
        df: pd.DataFrame,
        freq: Optional[str] = None,
        id_col: str = "unique_id",
        time_col: str = "ds",
        target_col: str = "y",
        level: Union[int, float] = 99,
        clean_ex_first: bool = True,
        validate_api_key: bool = False,
        date_features: Union[bool, List[str]] = False,
        date_features_to_one_hot: Union[bool, List[str]] = True,
        model: str = "timegpt-1",
        num_partitions: Optional[int] = None,
    ) -> fugue.AnyDataFrame:
        kwargs = dict(
            freq=freq,
            id_col=id_col,
            time_col=time_col,
            target_col=target_col,
            level=level,
            clean_ex_first=clean_ex_first,
            validate_api_key=validate_api_key,
            date_features=date_features,
            date_features_to_one_hot=date_features_to_one_hot,
            model=model,
        )
        schema = self._get_anomalies_schema(id_col=id_col, time_col=time_col)
        anomalies_df = self._distribute_method(
            method=self._detect_anomalies,
            df=df,
            kwargs=kwargs,
            schema=schema,
            num_partitions=num_partitions,
            id_col=id_col,
            X_df=None,
        )
        return anomalies_df

    def cross_validation(
        self,
        df: fugue.AnyDataFrame,
        h: int,
        freq: Optional[str] = None,
        id_col: str = "unique_id",
        time_col: str = "ds",
        target_col: str = "y",
        level: Optional[List[Union[int, float]]] = None,
        quantiles: Optional[List[float]] = None,
        finetune_steps: int = 0,
        finetune_loss: str = "default",
        clean_ex_first: bool = True,
        validate_api_key: bool = False,
        date_features: Union[bool, List[str]] = False,
        date_features_to_one_hot: Union[bool, List[str]] = True,
        model: str = "timegpt-1",
        n_windows: int = 1,
        step_size: Optional[int] = None,
        num_partitions: Optional[int] = None,
    ) -> fugue.AnyDataFrame:
        kwargs = dict(
            h=h,
            freq=freq,
            id_col=id_col,
            time_col=time_col,
            target_col=target_col,
            level=level,
            quantiles=quantiles,
            finetune_steps=finetune_steps,
            finetune_loss=finetune_loss,
            clean_ex_first=clean_ex_first,
            validate_api_key=validate_api_key,
            date_features=date_features,
            date_features_to_one_hot=date_features_to_one_hot,
            model=model,
            n_windows=n_windows,
            step_size=step_size,
        )
        schema = self._get_forecast_schema(
            id_col=id_col,
            time_col=time_col,
            level=level,
            quantiles=quantiles,
            cv=True,
        )
        fcst_df = self._distribute_method(
            method=self._cross_validation,
            df=df,
            kwargs=kwargs,
            schema=schema,
            num_partitions=num_partitions,
            id_col=id_col,
        )
        return fcst_df

    def _instantiate_nixtla_client(self):
        from nixtlats.nixtla_client import _NixtlaClient

        nixtla_client = _NixtlaClient(
            api_key=self.api_key,
            base_url=self.base_url,
            max_retries=self.max_retries,
            retry_interval=self.retry_interval,
            max_wait_time=self.max_wait_time,
        )
        return nixtla_client

    def _forecast(
        self,
        df: pd.DataFrame,
        kwargs,
    ) -> pd.DataFrame:
        nixtla_client = self._instantiate_nixtla_client()
        return nixtla_client._forecast(df=df, **kwargs)

    def _forecast_x(
        self,
        df: pd.DataFrame,
        X_df: pd.DataFrame,
        kwargs,
    ) -> pd.DataFrame:
        nixtla_client = self._instantiate_nixtla_client()
        return nixtla_client._forecast(df=df, X_df=X_df, **kwargs)

    def _detect_anomalies(
        self,
        df: pd.DataFrame,
        kwargs,
    ) -> pd.DataFrame:
        nixtla_client = self._instantiate_nixtla_client()
        return nixtla_client._detect_anomalies(df=df, **kwargs)

    def _cross_validation(
        self,
        df: pd.DataFrame,
        kwargs,
    ) -> pd.DataFrame:
        nixtla_client = self._instantiate_nixtla_client()
        return nixtla_client._cross_validation(df=df, **kwargs)

    @staticmethod
    def _get_forecast_schema(id_col, time_col, level, quantiles, cv=False):
        schema = f"{id_col}:string,{time_col}:datetime"
        if cv:
            schema = f"{schema},cutoff:datetime"
        schema = f"{schema},TimeGPT:double"
        if (level is not None) and (quantiles is not None):
            raise Exception("you should include `level` or `quantiles` but not both.")
        if level is not None:
            level = sorted(level)
            schema = f'{schema},{",".join([f"TimeGPT-lo-{lv}:double" for lv in reversed(level)])}'
            schema = f'{schema},{",".join([f"TimeGPT-hi-{lv}:double" for lv in level])}'
        if quantiles is not None:
            quantiles = sorted(quantiles)
            q_cols = [f"TimeGPT-q-{int(q * 100)}:double" for q in quantiles]
            schema = f'{schema},{",".join(q_cols)}'
        return Schema(schema)

    @staticmethod
    def _get_anomalies_schema(id_col, time_col):
        schema = f"{id_col}:string,{time_col}:datetime,anomaly:int"
        return Schema(schema)
