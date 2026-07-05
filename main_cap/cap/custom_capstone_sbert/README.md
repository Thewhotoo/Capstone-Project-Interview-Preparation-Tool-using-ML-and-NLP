---
tags:
- sentence-transformers
- sentence-similarity
- feature-extraction
- generated_from_trainer
- dataset_size:96
- loss:TripletLoss
base_model: sentence-transformers/all-MiniLM-L6-v2
widget:
- source_sentence: Context switching is the process of storing the state of a process
    or thread so that it can be restored and resumed at a later point. This allows
    multiple processes to share a single CPU resource. It involves saving the CPU
    registers, program counter, and other process-related information.
  sentences:
  - B-trees are great for most apps because they're good at finding data in a range
    or sorted order, and they can handle lots of unique values and frequent changes
    without slowing down.
  - Context switching is when the CPU decides to completely forget about all the running
    programs and start from scratch with a new one, losing all progress.
  - Context switching is like saving your game before switching to another game; the
    OS saves all the details of the current program so it can pick up exactly where
    it left off later.
- source_sentence: The Presentation Layer is responsible for data translation, encryption,
    and compression. It ensures that data is presented in a format that the Application
    Layer can understand.
  sentences:
  - Synchronization is like putting a 'Do Not Disturb' sign on a shared whiteboard.
    When one thread is writing important stuff on it, it locks it down so no other
    thread can scribble over it until it's done. This stops everyone from getting
    confused or messing up the information.
  - The Presentation Layer is where the actual electrical signals are transmitted
    over the network cable. It also handles the routing of data packets across different
    networks and provides network services directly to the end-user application.
  - The Presentation Layer is like a translator and security guard for your data.
    It makes sure that data from one computer can be understood by another, even if
    they use different formats. It also handles things like encrypting your data for
    security, like when you use HTTPS, and can compress data to make it smaller.
- source_sentence: CPU utilization is a scheduling criterion that measures how busy
    the CPU is, aiming to keep it as busy as possible.
  sentences:
  - It's how the OS figures out which program gets to run on the processor right now.
  - CPU utilization is a scheduling criterion that measures how much time a process
    spends waiting in the ready queue.
  - CPU utilization is all about keeping the processor working as much as possible.
- source_sentence: Deadlock handling strategies include deadlock prevention, deadlock
    avoidance, deadlock detection, and deadlock recovery. Prevention aims to ensure
    at least one of the necessary conditions never holds. Avoidance uses algorithms
    to ensure the system never enters an unsafe state. Detection involves periodically
    checking for deadlocks and then recovering. Recovery involves terminating processes
    or preempting resources.
  sentences:
  - The best way to handle deadlocks is to just let them happen as often as possible,
    and when they do, make sure every process involved gets even more resources so
    they can eventually finish.
  - To deal with deadlocks, you can either try to stop them from happening in the
    first place by making sure one of those conditions isn't met, or you can let them
    happen and then detect and fix them, maybe by killing a process or taking back
    a resource.
  - TCP/IP is the main language that computers use to talk to each other on the internet.
    It's a set of rules that makes sure data gets sent and received correctly, like
    how you send and receive emails or browse websites.
- source_sentence: Dense Index
  sentences:
  - Deadlock happens when a bunch of threads are all stuck waiting for each other
    to release something they need, like locks. It's like a traffic jam where everyone's
    waiting for the car in front to move, but no one can move.
  - A dense index only has an index entry for some records, making it sparse.
  - A dense index has an index entry for every single record in the database.
pipeline_tag: sentence-similarity
library_name: sentence-transformers
---

# SentenceTransformer based on sentence-transformers/all-MiniLM-L6-v2

This is a [sentence-transformers](https://www.SBERT.net) model finetuned from [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2). It maps sentences & paragraphs to a 384-dimensional dense vector space and can be used for retrieval.

## Model Details

### Model Description
- **Model Type:** Sentence Transformer
- **Base model:** [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) <!-- at revision c9745ed1d9f207416be6d2e6f8de32d1f16199bf -->
- **Maximum Sequence Length:** 256 tokens
- **Output Dimensionality:** 384 dimensions
- **Similarity Function:** Cosine Similarity
- **Supported Modality:** Text
<!-- - **Training Dataset:** Unknown -->
<!-- - **Language:** Unknown -->
<!-- - **License:** Unknown -->

### Model Sources

- **Documentation:** [Sentence Transformers Documentation](https://sbert.net)
- **Repository:** [Sentence Transformers on GitHub](https://github.com/huggingface/sentence-transformers)
- **Hugging Face:** [Sentence Transformers on Hugging Face](https://huggingface.co/models?library=sentence-transformers)

### Full Model Architecture

```
SentenceTransformer(
  (0): Transformer({'transformer_task': 'feature-extraction', 'modality_config': {'text': {'method': 'forward', 'method_output_name': 'last_hidden_state'}}, 'module_output_name': 'token_embeddings', 'architecture': 'BertModel'})
  (1): Pooling({'embedding_dimension': 384, 'pooling_mode': 'mean', 'include_prompt': True})
  (2): Normalize({})
)
```

## Usage

### Direct Usage (Sentence Transformers)

First install the Sentence Transformers library:

```bash
pip install -U sentence-transformers
```
Then you can load this model and run inference.
```python
from sentence_transformers import SentenceTransformer

# Download from the 🤗 Hub
model = SentenceTransformer("sentence_transformers_model_id")
# Run inference
sentences = [
    'Dense Index',
    'A dense index has an index entry for every single record in the database.',
    'A dense index only has an index entry for some records, making it sparse.',
]
embeddings = model.encode(sentences)
print(embeddings.shape)
# [3, 384]

# Get the similarity scores for the embeddings
similarities = model.similarity(embeddings, embeddings)
print(similarities)
# tensor([[1.0000, 0.7165, 0.5800],
#         [0.7165, 1.0000, 0.6404],
#         [0.5800, 0.6404, 1.0000]])
```
<!--
### Direct Usage (Transformers)

<details><summary>Click to see the direct usage in Transformers</summary>

</details>
-->

<!--
### Downstream Usage (Sentence Transformers)

You can finetune this model on your own dataset.

<details><summary>Click to expand</summary>

</details>
-->

<!--
### Out-of-Scope Use

*List how the model may foreseeably be misused and address what users ought not to do with the model.*
-->

<!--
## Bias, Risks and Limitations

*What are the known or foreseeable issues stemming from this model? You could also flag here known failure cases or weaknesses of the model.*
-->

<!--
### Recommendations

*What are recommendations with respect to the foreseeable issues? For example, filtering explicit content.*
-->

## Training Details

### Training Dataset

#### Unnamed Dataset

* Size: 96 training samples
* Columns: <code>sentence_0</code>, <code>sentence_1</code>, and <code>sentence_2</code>
* Approximate statistics based on the first 96 samples:
  |         | sentence_0                                                                         | sentence_1                                                                          | sentence_2                                                                         |
  |:--------|:-----------------------------------------------------------------------------------|:------------------------------------------------------------------------------------|:-----------------------------------------------------------------------------------|
  | type    | string                                                                             | string                                                                              | string                                                                             |
  | details | <ul><li>min: 4 tokens</li><li>mean: 52.12 tokens</li><li>max: 114 tokens</li></ul> | <ul><li>min: 16 tokens</li><li>mean: 48.81 tokens</li><li>max: 112 tokens</li></ul> | <ul><li>min: 17 tokens</li><li>mean: 37.45 tokens</li><li>max: 75 tokens</li></ul> |
* Samples:
  | sentence_0                                                                                                                                                                                                                                                                                                                                                                      | sentence_1                                                                                                                                                                                                                                                                                                                                           | sentence_2                                                                                                                                                                                      |
  |:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
  | <code>CCNA (Cisco Certified Network Associate) is a certification program from Cisco Systems that validates a user's ability to manage and optimize a business's network infrastructure. It covers a broad range of fundamentals, including network access, IP connectivity, IP services, security fundamentals, and automation and programmability.</code>                     | <code>CCNA is a Cisco certification that shows you know your stuff about setting up and managing computer networks, covering things like how networks connect, basic security, and even some newer automation stuff.</code>                                                                                                                          | <code>CCNA is a programming language used exclusively for developing operating systems, with no relation to network infrastructure or Cisco products.</code>                                    |
  | <code>A process is an independent program execution with its own memory space, while a thread is a unit of execution within a process that shares the process's memory. Coroutines are functions that can pause their execution and resume later, allowing for cooperative multitasking within a single thread.</code>                                                          | <code>A process is like a whole separate application running, with its own memory. A thread is like a smaller task within that application, sharing the same memory. Coroutines are even lighter, letting functions pause and resume within the same thread, like a cooperative dance.</code>                                                        | <code>A process is a small part of a thread, and coroutines are what make threads run. Threads are completely independent of processes and have their own memory.</code>                        |
  | <code>A page table is a data structure used by the virtual memory system to store the mapping between virtual addresses (logical page numbers) and physical addresses (physical page frames) in RAM. The Memory Management Unit (MMU) uses the page table to translate logical addresses generated by the CPU into physical addresses that can be used to access memory.</code> | <code>The page table is like a directory that the operating system uses. It keeps track of which page of a program is currently stored in which frame (a section of RAM). This helps the computer's hardware figure out the actual physical location in memory for any piece of data the program is asking for, based on its logical address.</code> | <code>The page table is a physical memory block that stores the entire program, and the operating system uses it to load pages from RAM into secondary storage when they are not needed.</code> |
* Loss: [<code>TripletLoss</code>](https://sbert.net/docs/package_reference/sentence_transformer/losses.html#tripletloss) with these parameters:
  ```json
  {
      "distance_metric": "TripletDistanceMetric.EUCLIDEAN",
      "triplet_margin": 5
  }
  ```

### Training Hyperparameters
#### Non-Default Hyperparameters

- `per_device_train_batch_size`: 16
- `per_device_eval_batch_size`: 16
- `num_train_epochs`: 4
- `multi_dataset_batch_sampler`: round_robin

#### All Hyperparameters
<details><summary>Click to expand</summary>

- `do_predict`: False
- `eval_strategy`: no
- `prediction_loss_only`: True
- `per_device_train_batch_size`: 16
- `per_device_eval_batch_size`: 16
- `gradient_accumulation_steps`: 1
- `eval_accumulation_steps`: None
- `torch_empty_cache_steps`: None
- `learning_rate`: 5e-05
- `weight_decay`: 0.0
- `adam_beta1`: 0.9
- `adam_beta2`: 0.999
- `adam_epsilon`: 1e-08
- `max_grad_norm`: 1
- `num_train_epochs`: 4
- `max_steps`: -1
- `lr_scheduler_type`: linear
- `lr_scheduler_kwargs`: None
- `warmup_ratio`: None
- `warmup_steps`: 0
- `log_level`: passive
- `log_level_replica`: warning
- `log_on_each_node`: True
- `logging_nan_inf_filter`: True
- `enable_jit_checkpoint`: False
- `save_on_each_node`: False
- `save_only_model`: False
- `restore_callback_states_from_checkpoint`: False
- `use_cpu`: False
- `seed`: 42
- `data_seed`: None
- `bf16`: False
- `fp16`: False
- `bf16_full_eval`: False
- `fp16_full_eval`: False
- `tf32`: None
- `local_rank`: -1
- `ddp_backend`: None
- `debug`: []
- `dataloader_drop_last`: False
- `dataloader_num_workers`: 0
- `dataloader_prefetch_factor`: None
- `disable_tqdm`: False
- `remove_unused_columns`: True
- `label_names`: None
- `load_best_model_at_end`: False
- `ignore_data_skip`: False
- `fsdp`: []
- `fsdp_config`: {'min_num_params': 0, 'xla': False, 'xla_fsdp_v2': False, 'xla_fsdp_grad_ckpt': False}
- `accelerator_config`: {'split_batches': False, 'dispatch_batches': None, 'even_batches': True, 'use_seedable_sampler': True, 'non_blocking': False, 'gradient_accumulation_kwargs': None}
- `parallelism_config`: None
- `deepspeed`: None
- `label_smoothing_factor`: 0.0
- `optim`: adamw_torch_fused
- `optim_args`: None
- `group_by_length`: False
- `length_column_name`: length
- `project`: huggingface
- `trackio_space_id`: trackio
- `ddp_find_unused_parameters`: None
- `ddp_bucket_cap_mb`: None
- `ddp_broadcast_buffers`: False
- `dataloader_pin_memory`: True
- `dataloader_persistent_workers`: False
- `skip_memory_metrics`: True
- `push_to_hub`: False
- `resume_from_checkpoint`: None
- `hub_model_id`: None
- `hub_strategy`: every_save
- `hub_private_repo`: None
- `hub_always_push`: False
- `hub_revision`: None
- `gradient_checkpointing`: False
- `gradient_checkpointing_kwargs`: None
- `include_for_metrics`: []
- `eval_do_concat_batches`: True
- `auto_find_batch_size`: False
- `full_determinism`: False
- `ddp_timeout`: 1800
- `torch_compile`: False
- `torch_compile_backend`: None
- `torch_compile_mode`: None
- `include_num_input_tokens_seen`: no
- `neftune_noise_alpha`: None
- `optim_target_modules`: None
- `batch_eval_metrics`: False
- `eval_on_start`: False
- `use_liger_kernel`: False
- `liger_kernel_config`: None
- `eval_use_gather_object`: False
- `average_tokens_across_devices`: True
- `use_cache`: False
- `prompts`: None
- `batch_sampler`: batch_sampler
- `multi_dataset_batch_sampler`: round_robin
- `router_mapping`: {}
- `learning_rate_mapping`: {}

</details>

### Training Time
- **Training**: 4.5 seconds

### Framework Versions
- Python: 3.12.13
- Sentence Transformers: 5.4.0
- Transformers: 5.0.0
- PyTorch: 2.10.0+cu128
- Accelerate: 1.13.0
- Datasets: 4.0.0
- Tokenizers: 0.22.2

## Citation

### BibTeX

#### Sentence Transformers
```bibtex
@inproceedings{reimers-2019-sentence-bert,
    title = "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks",
    author = "Reimers, Nils and Gurevych, Iryna",
    booktitle = "Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing",
    month = "11",
    year = "2019",
    publisher = "Association for Computational Linguistics",
    url = "https://arxiv.org/abs/1908.10084",
}
```

#### TripletLoss
```bibtex
@misc{hermans2017defense,
    title={In Defense of the Triplet Loss for Person Re-Identification},
    author={Alexander Hermans and Lucas Beyer and Bastian Leibe},
    year={2017},
    eprint={1703.07737},
    archivePrefix={arXiv},
    primaryClass={cs.CV}
}
```

<!--
## Glossary

*Clearly define terms in order to be accessible across audiences.*
-->

<!--
## Model Card Authors

*Lists the people who create the model card, providing recognition and accountability for the detailed work that goes into its construction.*
-->

<!--
## Model Card Contact

*Provides a way for people who have updates to the Model Card, suggestions, or questions, to contact the Model Card authors.*
-->