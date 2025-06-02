# Data Parallel Batch Gradient Descent

import logging
import asyncio
import torch
import stoilo.low_level as low_level

logger = logging.getLogger(__name__)


class DPBGDTrainer:
    def __init__(self, conn, model, loss_fn, optimizer_class, optimizer_kwargs,
                 flavor='44814764c91bf9ef426c4aa899df974f',
                 redundancy_options=None):
        self._conn = conn
        self._model = model
        self._loss_fn = loss_fn
        self._optimizer = optimizer_class(self._model.parameters(), **optimizer_kwargs)

        grad_shapes = {
            name: tuple(param.data.shape)
            for name, param in model.named_parameters()
        }

        class InitValidFunc:
            def __init__(self, grad_shapes):
                self._grad_shapes = grad_shapes
            
            def _check_grad_shape(self, grad_list, shape):
                if not shape:
                    return isinstance(grad_list, float)
                if not isinstance(grad_list, list) or len(grad_list) != shape[0]:
                    return False
                sub_shape = shape[1:]
                for item in grad_list:
                    if not self._check_grad_shape(item, sub_shape):
                        return False
                return True
            
            def __call__(self, returned):
                if not isinstance(returned['loss'], float):
                    return False
                for name, grad in returned['grads'].items():
                    if name not in self._grad_shapes:
                        return False
                    if not self._check_grad_shape(grad, self._grad_shapes[name]):
                        return False
                return True

        class CompareValidFunc:
            def __init__(self, rel_tol=1e-6, abs_tol=1e-8):
                self._rel_tol = rel_tol
                self._abs_tol = abs_tol

            def _compare_nested(self, a, b):
                import math
                if isinstance(a, list):
                    return all(self._compare_nested(x, y) for x, y in zip(a, b))
                else:
                    return math.isclose(a, b, rel_tol=self._rel_tol, abs_tol=self._abs_tol)

            def __call__(self, returned_1, returned_2):
                import math
                if not math.isclose(returned_1['loss'], returned_2['loss'], rel_tol=self._rel_tol, abs_tol=self._abs_tol):
                    return False
                return self._compare_nested(returned_1['grads'], returned_2['grads'])

        self._init_valid_func = InitValidFunc(grad_shapes)
        self._compare_valid_func = CompareValidFunc()
        self._flavor = flavor
        if redundancy_options is None:
            redundancy_options = low_level.redundancy.CreateOptions(
                min_quorum=1,
                delay_bound=600
            )
        self._redundancy_options = redundancy_options
    
    async def epoch_create_work(self, data_loader):
        def worker_func(kwargs):
            import torch

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            model = kwargs["model"].to(device).train()
            data = kwargs["batch"][0].to(device)
            target = kwargs["batch"][1].to(device)
            loss_fn = kwargs["loss_fn"]    

            output = model(data)
            loss = loss_fn(output, target)
            loss.backward()

            grads = {
                name: param.grad.detach().cpu().tolist()
                for name, param in model.named_parameters()
                if param.grad is not None
            }

            return {'grads': grads, 'loss': loss.item()}

        tasks = []
        for batch in data_loader:
            task = self._conn.create_task(
                func=worker_func,
                kwargs={
                    "model": self._model,
                    "batch": batch,
                    "loss_fn": self._loss_fn,
                },
                init_valid_func=self._init_valid_func,
                compare_valid_func=self._compare_valid_func,
                flavor=self._flavor,
                redundancy_options=self._redundancy_options,
            )
            tasks.append(task)
        print(f"Created {len(tasks)} tasks")

        return await asyncio.gather(*(t.submit() for t in tasks))

    async def epoch_aggregate_results(self, works):
        results = await asyncio.gather(*(t.result() for t in works))

        self._optimizer.zero_grad(set_to_none=True)
        total_loss = 0

        param_dict = dict(self._model.named_parameters())
        for result in results:
            if isinstance(result, low_level.UserError) or isinstance(result, low_level.SystemError):
                raise result
            for name, partial_grad_raw in result['grads'].items():
                partial_grad = torch.tensor(partial_grad_raw)
                # print(f"partial_grad mean: {partial_grad.mean()}")
                p = param_dict[name]
                if p.grad is None:
                    p.grad = torch.zeros_like(p.data)
                p.grad.add_(partial_grad)
            total_loss += result['loss']
        
        for p in self._model.parameters():
            if p.grad is not None:
                p.grad.div_(len(results))
        total_loss /= len(results)

        before = {n: p.data.clone() for n, p in self._model.named_parameters()}
        self._optimizer.step()
        after  = {n: p.data.clone() for n, p in self._model.named_parameters()}
        diff_list = []
        for name in before:
            diff = (after[name] - before[name]).norm().item()
            diff_list.append((name, diff))
        print(f"update norm: {diff_list}")

        return self._model, total_loss

    async def epoch(self, data_loader):
        works = await self.epoch_create_work(data_loader)
        return await self.epoch_aggregate_results(works)
