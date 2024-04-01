import logging
import os
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple, Union

import torch
from accelerate.state import PartialState
from accelerate.utils.dataclasses import DistributedType
from transformers.training_args_seq2seq import Seq2SeqTrainingArguments
from transformers.utils import cached_property

import atorch
from atorch.utils.trainer_utils import ATORCHSCHEDULER_NAMES, SCHEDULER_NAMES, AtorchSchedulerType

logger = logging.getLogger(__name__)


@dataclass
class AtorchArguments(Seq2SeqTrainingArguments):
    # ATorch config
    save_load_by_streaming: bool = field(default=False, metadata={"help": "Accelerate save/load speed."})
    ignore_dryrun_on_load_strategy: bool = field(
        default=True, metadata={"help": "Whether to ignore dryrun when calling `auto_accelerate`."}
    )
    atorch_parallel_mode: bool = field(
        default=True,
        metadata={
            "help": (
                "Whether to use `parallel_mode` optimize in ATorch. (useful only when " "`use_auto_accelerate` is True)"
            )
        },
    )
    atorch_opt: str = field(
        default="fsdp", metadata={"help": "ATorch training optimization strategy. Support 'fsdp' and 'ddp'."}
    )
    atorch_module_replace: bool = field(
        default=True, metadata={"help": "Whether to use `module_replace` optimize in ATorch."}
    )
    save_base_model: bool = field(
        default=False, metadata={"help": "Whether to save base model. Useful only when `peft_type` field is passed."}
    )
    use_atorch_dataloader: bool = field(
        default=True,
        metadata={
            "help": (
                "Whether to use `auto_accelerate()` to wrap dataloader."
                "If you want to use Trainer's get_train_dataloader(), set --use_atorch_dataloader False."
            )
        },
    )
    shuffle: bool = field(default=True, metadata={"help": "If `True` (default), dataloader will shuffle the data."})
    optim_func: Optional[Callable] = field(
        default=torch.optim.AdamW,
        metadata={
            "help": (
                "optim_func can be a pytorch built-in optimizer function or a user-defined function, with params and"
                "optim_args as arguments. such as:"
                "def optim_func(parameters, **optim_args):"
                "    return optim.SGD(parameters, **optim_args)"
                "The optimizer will be created by optim_func(model.parameters(), **optim_args)."
            )
        },
    )
    optim_args: Optional[Dict] = field(
        default=None,
        metadata={"help": 'A dict of arguments used for optim, such as: optim_args = {"lr": 0.01, "momentum": 0.9}'},
    )
    optim_param_func: Optional[Callable] = field(
        default=None,
        metadata={"help": "Function returns an optimizer's parameters if users want to specify per-parameter options."},
    )
    loss_func: Optional[Callable] = field(
        default=None,
        metadata={
            "help": (
                "loss function for loss calculation from model input and output, such as:"
                "def loss_func(input, output):"
                "    loss = nn.MSELoss()"
                '    return loss(input["label"], output)'
                "This function either returns a loss value, or a list/tuple with the first value as loss."
            )
        },
    )
    prepare_input: Optional[Callable] = field(
        default=None,
        metadata={
            "help": (
                "This is a function taken data and device as arguments."
                "Call this function on data generated from dataloader before model input."
            )
        },
    )
    model_input_format: Optional[str] = field(
        default=None,
        metadata={
            "help": (
                "The format in which the input data is passed to the model."
                "If model_input_format=None, data is passed to model by `model(data)`."
                "If model_input_format='unpack_sequence', `model(*data)`."
                "If model_input_format='unpack_dict', `model(**data)`."
            )
        },
    )
    distributed_sampler_cls: Optional[Callable] = field(
        default=None,
        metadata={
            "help": "if not None, custom distributed sampler with same interface as pytorch's DistributedSampler."
        },
    )
    excluded: Optional[List[str]] = field(
        default=None, metadata={"help": "A list of optimization method names, which should NOT be used."}
    )
    included: Optional[List[str]] = field(
        default=None, metadata={"help": "A list of optimization method names, which should NOT be used."}
    )
    finetune_strategy: bool = field(
        default=False, metadata={"help": "If True and `load_strategy` is not None, finetune the loaded strategy."}
    )
    save_strategy_to_file: Optional[str] = field(
        default=None, metadata={"help": "If not None, a file name for saving the acceleration strategy."}
    )

    atorch_checkpoint_cls: Optional[Tuple[Union[Callable, str]]] = field(
        default=None,
        metadata={
            "help": (
                "Tuple of module classes for gradient checkpointing. Applicable when --gradient_checkpointing is set."
            )
        },
    )

    use_default_data_collator: bool = field(
        default=False,
        metadata={
            "help": (
                "Whether to use default data collator DataCollatorWithPadding which may decrease the speed of "
                "data retrieval."
            )
        },
    )

    ignore_write_errors: bool = field(
        default=False, metadata={"help": ("Whether to ignore write errors when writting to disk.")}
    )

    async_save: bool = field(default=False, metadata={"help": ("Whether to use multiprocess to save model.")})

    atorch_lr_scheduler_type: Optional[Union[AtorchSchedulerType, str]] = field(
        default=None,
        metadata={"help": "The custom scheduler type to use."},
    )

    # ATorch FSDP config
    atorch_wrap_cls: Optional[Tuple[Union[Callable, str]]] = field(
        default=None, metadata={"help": "Tuple of module classes to wrap with fsdp."}
    )
    cpu_offload: bool = field(default=False, metadata={"help": "Whether to use cpu_offload"})
    use_orig_params: bool = field(default=True, metadata={"help": "Whether to use_orig_params"})
    wrap_trainable_outmost: bool = field(default=False, metadata={"help": "Whether to wrap_trainable_outmost"})
    sync_module_states: bool = field(default=True, metadata={"help": "Whether to sync_module_states"})
    limit_all_gathers: bool = field(default=True, metadata={"help": "Whether to limit_all_gathers"})
    forward_prefetch: bool = field(default=True, metadata={"help": "Whether to forward_prefetch"})

    # ATorch amp config
    skip_if_nonfinite: bool = field(default=True, metadata={"help": ("Whether to skip if nonfinite.")})

    # Other config
    max_shard_size: str = field(
        default="10GB",
        metadata={
            "help": (
                "The maximum size for a checkpoint before being sharded. " "Used on PreTrainedModel.save_pretrained()."
            )
        },
    )

    @cached_property
    def _setup_devices(self) -> "torch.device":
        logger.info("PyTorch: setting up devices")

        if not torch.distributed.is_initialized():
            atorch.init_distributed(
                os.getenv("TORCH_DISTRIBUTED_BACKEND", "nccl"), timeout=timedelta(seconds=self.ddp_timeout)
            )

        # Set distributed_state
        self.distributed_state = PartialState(backend=self.ddp_backend, timeout=timedelta(seconds=self.ddp_timeout))
        self.distributed_state.distributed_type = DistributedType.MULTI_GPU
        self.distributed_state.num_processes = torch.distributed.get_world_size()
        self.distributed_state.process_index = torch.distributed.get_rank()
        self.distributed_state.local_process_index = int(os.environ.get("LOCAL_RANK", -1))
        self.distributed_state.device = torch.device("cuda", self.distributed_state.local_process_index)

        self._n_gpu = 1
        device = self.distributed_state.device
        torch.cuda.set_device(device)
        return device

    def to_dict(self):
        """
        Serializes this instance while replace `Enum` by their values and `Callable` by dictionaries (for JSON
        serialization support). It obfuscates the token values by removing their value.
        """
        # filter out fields that are defined as field(init=False)
        d = super().to_dict()
        for k, v in d.items():
            if isinstance(v, Callable):
                d[k] = v.__name__ if hasattr(v, "__name__") else str(v)
            elif isinstance(v, list) and len(v) > 0:
                if isinstance(v[0], Enum):
                    d[k] = [x.value for x in v]
                elif isinstance(v[0], Callable):
                    d[k] = [x.__name__ if hasattr(x, "__name__") else str(x) for x in v]
            elif isinstance(v, tuple) and len(v) > 0 and isinstance(v[0], Callable):
                v = [x.__name__ if hasattr(x, "__name__") else str(x) for x in v]
                d[k] = tuple(v)
        return d

    def __post_init__(self):
        # Check arguments in transformers.training_args.TrainingArguments
        if self.report_to is not None:
            if self.report_to == "all" or self.report_to == ["all"]:
                logger.info("AtorchTrainer only support TensorBoard to report the results and logs.")
            elif self.report_to != "tensorboard" and self.report_to != ["tensorboard"]:
                raise ValueError("AtorchTrainer only support TensorBoard to report the results and logs.")

        # check lr_scheduler_type
        if self.atorch_lr_scheduler_type is not None and self.atorch_lr_scheduler_type not in ATORCHSCHEDULER_NAMES:
            raise ValueError(
                f"lr_scheduler_type={self.atorch_lr_scheduler_type} is invalid, please select one of "
                f"{SCHEDULER_NAMES + ATORCHSCHEDULER_NAMES}."
            )

        if self.atorch_wrap_cls is not None and not isinstance(self.atorch_wrap_cls, tuple):
            raise ValueError(f"atorch_wrap_cls has {type(self.atorch_wrap_cls)} type, required tuple type.")

        if self.atorch_checkpoint_cls is not None and not isinstance(self.atorch_checkpoint_cls, tuple):
            raise ValueError(f"atorch_checkpoint_cls has {type(self.atorch_checkpoint_cls)} type, required tuple type.")

        Seq2SeqTrainingArguments.__post_init__(self)
