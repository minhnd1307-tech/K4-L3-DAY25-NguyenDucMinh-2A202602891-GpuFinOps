# Báo cáo Kỹ thuật: Tối ưu hóa Chi phí GPU FinOps tại NimbusAI

**Tác giả:** FinOps Lead Engineer  
**Hệ thống:** NimbusAI Infrastructure Platform  
**Kỳ đánh giá:** Tháng 06/2026 (Monthly Baseline & Optimization)  

---

## 1. Tóm tắt Điều hành: Baseline vs. Optimized

NimbusAI đang đối mặt với tình trạng chi phí hạ tầng GPU tăng mất kiểm soát do mô hình triển khai mặc định (naive deployment): toàn bộ workload chạy trên các GPU On-Demand đắt đỏ, tất cả prompt đều nạp vào model lớn, và thiếu cơ chế thu hồi tài nguyên nhàn rỗi.

Bằng việc áp dụng toàn diện khung phương pháp luận **GPU FinOps**, chúng tôi đã tối ưu hóa đồng thời trên cả 2 tầng: **Tầng Hạ tầng Phần cứng (Compute Infrastructure)** và **Tầng Kiến trúc Phục vụ Mô hình (Model Serving & Inference Architecture)**.

### Bảng cân đối tài chính tổng thể

| Chỉ số | Baseline (Trước tối ưu) | Optimized (Sau tối ưu) | Mức cắt giảm | % Tiết kiệm |
|---|---|---|---|---|
| **Tổng chi phí GPU / tháng** | $27,133 | $14,626 | -$12,507 | **46.1%** |
| **Chi phí Inference / ngày** | $48.87 / ngày | $8.48 / ngày | -$40.39 / ngày | **82.6%** |
| **Đơn giá suy luận (`$/1M-token`)** | **$6.488** / 1M-token | **$1.126** / 1M-token | -$5.362 / 1M-token | **82.6%** |
| **Chi phí Workload Training & Batch** | $25,667 / tháng | $15,627 / tháng | -$10,040 / tháng | **39.1%** |
| **Thất thoát GPU Idle** | $600 / tháng | $0 / tháng | -$600 / tháng | **100.0%** |
| **Lãng phí GPU Over-provisioning** | $655 / tháng | $0 / tháng | -$655 / tháng | **100.0%** |

*Biểu đồ trực quan hóa đóng góp của từng đòn bẩy tiết kiệm đã được tự động kết xuất tại file `outputs/savings.png`.*

---

## 2. Phân tích Chi tiết Từng Đòn bẩy Tiết kiệm (FinOps Levers)

Khoản tiết kiệm **$12,507 / tháng** đến từ sự kết hợp của 4 đòn bẩy kỹ thuật:

```
+---------------------------------------------------------------------------------+
| Phân bổ Tiết kiệm:                                                              |
| [========================================] Purchasing (Spot/Reserved): $10,040 (80.3%)
| [====] Inference (Cascade/Cache/Batch): $1,212 (9.7%)                           |
| [==] Right-sizing MBU / Util-lies: $655 (5.2%)                                  |
| [==] Loại bỏ GPU Idle qua đêm: $600 (4.8%)                                      |
+---------------------------------------------------------------------------------+
```

### 2.1. Đòn bẩy 1: Chiến lược Mua sắm (Purchasing Strategy) — Tiết kiệm $10,040/tháng (80.3%)
- **Cơ chế:** Phân loại 8 workload chính theo tỷ lệ chiếm dụng (duty cycle) và tính chất có thể gián đoạn (interruptibility):
  - **Reserved Instances (Cam kết 3 năm, chiết khấu 45%):** Áp dụng cho các dịch vụ cốt lõi chạy liên tục 24/7 có `duty_cycle ≥ 55%` (điểm hòa vốn `break_even = 1 - 0.45 = 55%`). Gồm 3 job: `job-infer-chat` (A10G), `job-infer-rag` (A100), `job-infer-search` (L4).
  - **Spot Instances (Chiết khấu 40% – 60%):** Áp dụng cho các job huấn luyện batch và offline có thể gián đoạn (`interruptible = 1`), kết hợp cơ chế lưu checkpoint định kỳ. Gồm 5 job: `job-train-llm`, `job-train-embed`, `job-finetune`, `job-dev-sandbox`, `job-batch-eval`.
- **Đánh giá:** Đây là đòn bẩy đóng góp số tiền tuyệt đối lớn nhất do chi phí huấn luyện phân tán trên H100 chiếm tỷ trọng chi phối trong ngân sách.

### 2.2. Đòn bẩy 2: Tối ưu hóa Suy luận (Inference Levers) — Tiết kiệm $1,212/tháng (82.6% chi phí suy luận)
Chỉ số đơn vị giảm từ **$6.488** xuống còn **$1.126 / 1M-token** nhờ kết hợp 3 kỹ thuật:
1. **Cascade Routing:** Chuyển 80% truy vấn đơn giản sang model `small` ($0.20 in / $0.40 out), chỉ giữ 20% câu hỏi phức tạp trên model `large` ($3.00 in / $15.00 out). Chênh lệch giá input 15× và output 37.5× giúp giảm tới 70% hóa đơn gốc.
2. **Prompt Caching:** Tận dụng System Prompt tĩnh trong Chat và RAG; phần input tokens đọc từ cache được giảm 90% giá (`cache_discount = 0.10`).
3. **Batch API:** Gom các job không đòi hỏi độ trễ thời gian thực (đánh giá hàng đêm `nightly-eval`) để nhận chiết khấu 50% (`batch_discount = 0.50`).
- **Hiệu ứng nhân dồn (Discount Stack):** Với request thỏa mãn cả Batch và 100% Cache, chi phí chỉ còn `0.50 × 0.10 = 0.05` (tiết kiệm **95%** chi phí input).

### 2.3. Đòn bẩy 3: Khắc phục Over-provisioning & Right-sizing — Tiết kiệm $655/tháng (5.2%)
Hạ cấu hình các GPU bị định cỡ quá mức dựa trên phân tích MBU thực tế (chi tiết đối soát phạm vi tại mục 4.1).

### 2.4. Đòn bẩy 4: Tự động Tắt máy Nhàn rỗi (Kill Idle GPUs) — Tiết kiệm $600/tháng (4.8%)
Phát hiện node `gpu-h100-5` bị bỏ trống 8 giờ liên tục mỗi đêm (`gpu_util < 10%`). Triển khai auto-scaler hạ node tự động sau 15 phút idle, thu hồi trọn vẹn $20/ngày.

---

## 3. Bản chất Kỹ thuật của "GPU-Util Lie" & Tác động Tài chính

### 3.1. Tại sao `GPU-Util %` là một "Lời nói dối"?
Lệnh `nvidia-smi` báo cáo chỉ số `GPU-Util` dựa trên mẫu thời gian: tỷ lệ phần trăm thời gian có ít nhất một kernel đang active trên GPU. 
- `GPU-Util` **chỉ đo thời gian xung nhịp bận rộn**, hoàn toàn **không đo** xem các nhân tính toán Tensor Cores hay Streaming Multiprocessors (SM) có đang sinh ra các phép tính hữu ích ở tốc độ tối đa hay không.

### 3.2. Bằng chứng thực nghiệm tại NimbusAI
Trong 11 GPU được giám sát, chúng tôi phát hiện 2 ca bệnh điển hình:
1. **`gpu-h100-4` (Trọng điểm):**
   - Báo cáo `GPU-Util = 98.2%` (ngỡ như đang chạy hết công suất).
   - Nhưng **MFU chỉ đạt 0.194** (chưa đầy 20% năng lực tính toán đỉnh) và **MBU = 0.207**.
2. **`gpu-a10g-1`:**
   - Báo cáo `GPU-Util = 96.9%`, nhưng **MFU chỉ đạt 0.268** (< 30%).

### 3.3. Cơ chế gây nghẽn bên dưới
- **Memory Stall (Nghẽn bộ nhớ):** Kernel chiếm giữ SM nhưng các thread bị dừng chờ nạp dữ liệu từ HBM do kích thước batch nhỏ hoặc giải thuật token decoding.
- **Kernel Launch Overhead:** Chạy quá nhiều kernel nhỏ lẻ khiến thời gian CPU chuẩn bị và đẩy lệnh lấn át thời gian tính toán thực.
- **I/O & Data Loader Bottleneck:** Pipeline nạp dữ liệu qua PCIe không kịp cung cấp batch cho GPU.

### 3.4. Tác động tài chính
NimbusAI trả đủ **$2.50 / giờ** cho `gpu-h100-4` ($1,800/tháng) nhưng chỉ nhận lại năng lực tương đương một GPU cấp thấp ($1.79/giờ hoặc thấp hơn). Việc chỉ nhìn vào dashboard `nvidia-smi` 98% khiến đội ngũ kỹ thuật lầm tưởng cần mua thêm GPU, trong khi thực tế hạ tầng đang bị lãng phí nghiêm trọng.

---

## 4. Báo cáo Hai Phần Mở rộng Nâng cao (Extensions 2 & 3)

### 4.1. Extension 2: Data-Driven Right-sizing theo MBU & VRAM Economics
*(Triển khai tại `missions/m1_efficiency_audit.py`)*

#### Thuật toán Đề xuất Động theo Dữ liệu (Không Hardcode)
Hệ thống không ánh xạ cứng theo mã GPU ID, mà đánh giá trực tiếp dựa trên hồ sơ tài nguyên đỉnh thực tế của từng node trong 24 giờ:
1. **Ràng buộc Chi phí:** GPU ứng viên phải có giá On-Demand thấp hơn GPU hiện tại (`cand_price < cur_price`).
2. **Ràng buộc Bộ nhớ (Chống lỗi OOM):** Dung lượng HBM của ứng viên phải lớn hơn hoặc bằng mức VRAM đỉnh ghi nhận (`cand_vram >= max_mem_gb`).
3. **Ràng buộc Băng thông (Bảo đảm SLA Độ trễ):** Băng thông cực đại của ứng viên phải đáp ứng băng thông đỉnh thực tế kèm **15% biên an toàn** (`cand_peak_bw >= max_bw_tbs * 1.15`).
4. **Ràng buộc Năng lực Tính toán:** Năng lực tính toán đỉnh của ứng viên phải đáp ứng tải TFLOPS đỉnh thực tế kèm 10% biên an toàn (`cand_peak_tflops >= max_tflops * 1.10`).

*Kiểm chứng độ tin cậy của thuật toán (Stress-Test):* Nếu một node A10G có nhu cầu băng thông đạt `0.59 TB/s`, thuật toán sẽ **từ chối ngay lập tức đề xuất L4** (vì L4 chỉ có đỉnh `0.30 TB/s` < `0.59 * 1.15 = 0.678 TB/s`), ngăn ngừa triệt để nguy cơ vi phạm SLA độ trễ.

#### Bảng Đơn giá Kinh tế Bộ nhớ (VRAM Economics) trong Catalog

| GPU Type | VRAM (GB) | Peak BW (TB/s) | On-Demand ($/hr) | Đơn giá VRAM (`$/GB-hr`) | Đơn giá Băng thông (`$/TBps-hr`) |
|---|---|---|---|---|---|
| **MI300X** | 192.0 | 5.30 | $1.95 | **$0.01016** (Rẻ nhất) | $0.3679 |
| **A100** | 80.0 | 2.00 | $1.79 | **$0.02237** | $0.8950 |
| **B200** | 192.0 | 8.00 | $5.09 | $0.02651 | $0.6362 |
| **H200** | 141.0 | 4.80 | $3.95 | $0.02801 | $0.8229 |
| **H100** | 80.0 | 3.35 | $2.50 | $0.03125 | $0.7463 |
| **L4** | 24.0 | 0.30 | $0.80 | $0.03333 | $2.6667 |
| **A10G** | 24.0 | 0.60 | $1.00 | $0.04167 | $1.6667 |

#### Đề xuất Right-sizing Động từ Dữ liệu Telemetry

| GPU ID | GPU Hiện tại | GPU Đề xuất | Đỉnh VRAM | Đỉnh BW (TB/s) | Giá Cũ ($/hr) | Giá Mới ($/hr) | Tiết kiệm Active (tháng) | Tiết kiệm 24h (tháng) | Thuộc Nhóm Util-Lie? |
|---|---|---|---|---|---|---|---|---|---|
| `gpu-h100-4` | H100 (80GB) | **A100 (80GB)** | 67.0 GB | 0.908 TB/s | $2.50 | $1.79 | **$511.20** | $511.20 | **Có** (Util 98.2%, MFU 0.194) |
| `gpu-a10g-1` | A10G (24GB) | **L4 (24GB)** | 20.4 GB | 0.212 TB/s | $1.00 | $0.80 | **$144.00** | $144.00 | **Có** (Util 96.9%, MFU 0.268) |
| `gpu-a10g-0` | A10G (24GB) | **L4 (24GB)** | 20.3 GB | 0.182 TB/s | $1.00 | $0.80 | **$144.00** | $144.00 | Không (Util 25.0%, MBU 0.235) |
| `gpu-h100-5` | H100 (80GB) | **MI300X (192GB)** | 66.3 GB | 1.538 TB/s | $2.50 | $1.95 | **$264.00** (16h active) | $396.00 (24h) | Không (Util 61.1%, MBU 0.271) |

#### Thống nhất & Đối soát Hai Phạm vi Tiết kiệm (Reconciliation of Scopes)
- **Phạm vi 1 — Báo cáo Tổng hợp M5 (Core Lever: Right-size Util-Lies Only):**  
  Chỉ tính trên 2 GPU bị gắn cờ "GPU-Util Lie" (`gpu-h100-4` và `gpu-a10g-1`), đóng góp đúng **$655.20 / tháng** (~**$655**) vào bảng tiết kiệm tổng thể của M5. M5 hiện lấy trực tiếp giá trị này từ engine M1 để bảo đảm tính nhất quán 100%.
- **Phạm vi 2 — Mở rộng Extension 2 (Toàn bộ Fleet Memory-Bound kết hợp Tắt Idle):**  
  Khi mở rộng sang toàn bộ fleet, thuật toán đề xuất thêm `gpu-a10g-0` và `gpu-h100-5`. Để **tránh tính trùng lặp (double-counting)** với đòn bẩy Kill Idle (đã thu hồi 8 giờ/ngày = $600/tháng của `gpu-h100-5`), khoản tiết kiệm right-sizing của `gpu-h100-5` chỉ tính trên 16 giờ hoạt động còn lại: `$0.55 × 16h × 30 ngày = $264.00 / tháng`.  
  Tổng tiết kiệm right-sizing toàn fleet khi kết hợp là:  
  `$511.20 + $144.00 + $144.00 + $264.00 = $1,063.20 / tháng`.  
  *(Nếu xét kịch bản standalone chạy đủ 24 giờ không tắt idle, tổng tiết kiệm là $1,195.20 / tháng).*

> **Trả lời câu hỏi phản biện: "Tại sao không chỉ chọn GPU rẻ nhất theo `$/GPU-hr`?"**  
> Việc chọn GPU rẻ nhất theo giờ (ví dụ L4 với $0.80/hr) mà bỏ qua đặc tính kỹ thuật là sai lầm nghiêm trọng trong AI FinOps:  
> 1. **Nguy cơ Out-Of-Memory (OOM):** L4 chỉ có 24GB VRAM. Nếu đưa một mô hình 70B (yêu cầu ít nhất 40–80GB VRAM) vào L4, hệ thống sẽ sập OOM ngay lập tức.  
> 2. **Vi phạm SLA độ trễ:** L4 chỉ có băng thông 0.3 TB/s (kém hơn 11× so với H100). Trong workload LLM Decode vốn bị nghẽn băng thông bộ nhớ (memory-bound), băng thông thấp sẽ khiến thời gian sinh mỗi token (TPOT) tăng vọt.  
> **Nguyên tắc FinOps chuẩn:** Phải tối ưu hóa dựa trên điểm cân bằng giữa dung lượng VRAM thực tế và băng thông `peak_bw_tbs` cần thiết!

---

### 4.2. Extension 3: Kinh tế học Prompt Cache (`cache_is_worth_it()`)
*(Triển khai tại `finops/pricing.py` và tích hợp tại `missions/m2_inference_levers.py`)*

#### Công thức Điểm hòa vốn (Break-even Reads Formula)
Việc ghi dữ liệu vào Prompt Cache tiêu tốn chi phí khởi tạo ban đầu (`write_cost`). Caching chỉ thực sự tiết kiệm tiền khi phần tiết kiệm tích lũy qua các lần đọc sau lớn hơn chi phí ghi:

```
Tiết kiệm mỗi lần đọc = base_read_cost × (1 - read_discount)
Tổng tiết kiệm = số_lần_đọc × Tiết kiệm mỗi lần đọc
Điều kiện hòa vốn: số_lần_đọc ≥ write_cost / [base_read_cost × (1 - read_discount)]
```

#### Kết quả Tính toán Điểm hòa vốn theo Model Tier

| Model Tier | Giá Input Chuẩn (`$/1M`) | Break-Even Reads (Ghi chuẩn 1.0×) | Break-Even Reads (Ghi có phụ phí 1.25×) |
|---|---|---|---|
| **Small Tier** | $0.20 | **1.11 lần đọc** | **1.39 lần đọc** |
| **Large Tier** | $3.00 | **1.11 lần đọc** | **1.39 lần đọc** |

#### Mô hình hóa Giả định & Phân tích Độ nhạy (Simulation Modeling & Sensitivity)
- **Lưu ý về Dữ liệu:** Tập dữ liệu `token_usage.csv` không lưu vết định danh `prefix_id` và thời gian sống `cache_ttl`. Do đó, chúng tôi xây dựng mô hình giả định có cơ sở:
  - Giả định cơ sở (Baseline Hypothesis): Các truy vấn trong cùng dự án (`assistant/chat` và `rag/doc-qa`) chia sẻ cùng một System Prompt và bộ tài liệu RAG theo chu kỳ giờ. Với lưu lượng 21.5 – 30.5 request/giờ, nếu cache tồn tại tối thiểu 1 giờ thì tần suất tái sử dụng ước tính đạt ~20–30 reads/prefix.
  - Phân tích độ nhạy (Sensitivity Analysis): Điểm hòa vốn toán học thực tế chỉ cần **1.11 reads** (hoặc **1.39 reads** nếu nhà cung cấp tính phụ phí ghi 25%).
  - Bất kể hệ thống đạt 20 reads/prefix hay chỉ đạt 2 reads/prefix trong thực tế, chỉ cần prefix được tái sử dụng từ **lần thứ 2 trở lên (`≥ 2 reads`)**, Prompt Caching đã chắc chắn sinh lời.
  - Nếu trong production một prefix chỉ được đọc đúng 1 lần (one-off prompt), hàm `cache_is_worth_it()` sẽ trả về `False` và loại bỏ phần cache để tránh lãng phí chi phí ghi ban đầu.

---

## 5. Phân bổ Chi phí & Quản trị Bền vững (Sustainability & Governance)

### 5.1. Phân bổ Chi phí theo Team (Showback & Chargeback)
- **Độ phủ nhãn (Tag Coverage):** Đạt **92%** (vượt ngưỡng tiêu chuẩn 80% của FinOps Foundation).
- **Cổng thanh toán nội bộ (Chargeback Gate):** Đã chính thức mở (`chargeback_ready = True`), cho phép phòng tài chính thu hồi chi phí trực tiếp từ ngân sách của từng bộ phận:
  - Team Assistant: $2.59 / ngày (~$77.7 / tháng)
  - Team Search: $2.49 / ngày (~$74.7 / tháng)
  - Team Eval: $1.79 / ngày (~$53.7 / tháng)
  - Team RAG: $1.60 / ngày (~$48.0 / tháng)
- **Chuẩn hóa dữ liệu:** Đã xuất 50 dòng hóa đơn mẫu đạt chuẩn **FOCUS** ra file `outputs/focus_export.csv`.

### 5.2. Tính Bền vững & Phát thải Carbon (Đối soát chuẩn xác dữ liệu mã nguồn)
Căn cứ dữ liệu định nghĩa trong `finops/sustainability.py`:

| Khu vực (Region) | Cường độ Carbon (`gCO2/kWh`) | Đơn giá Điện (`$/kWh`) | Đánh giá FinOps |
|---|---|---|---|
| `us-east-1` (Hiện tại) | 380 | $0.120 | Lưới điện hóa thạch, chi phí trung bình cao |
| `europe-north1` (Bắc Âu) | **30** | $0.090 | **Sạch nhất (Cleanest):** Giảm **92.1%** carbon so với `us-east-1` |
| `us-east-wa` (Washington) | 90 | **$0.055** | **Rẻ nhất (Cheapest):** Giảm **54.2%** chi phí điện so với `us-east-1` |
| `us-west-2` (Oregon) | 120 | $0.070 | Nguồn thủy điện, chi phí và carbon ở mức tốt |
| `europe-central2` (Ba Lan) | 660 | $0.180 | Ô nhiễm nhất và đắt nhất (cần tránh) |

- **Chỉ số năng lượng hiện tại:** `0.24 Wh / query` (độ dài trung vị 800 tokens).
- **Cường độ phát thải hiện tại tại `us-east-1`:** `0.091 gCO2e / query`.
- **Phân tích Đánh đổi Thực tế (FinOps Trade-off):**
  - Vùng sạch nhất là `europe-north1` (30 gCO2/kWh, cắt giảm 92.1% carbon), nhưng đơn giá điện ($0.09/kWh) không phải rẻ nhất.
  - Vùng có giá điện rẻ nhất là `us-east-wa` ($0.055/kWh, rẻ hơn 54.2%), đồng thời mức phát thải 90 gCO2/kWh vẫn sạch hơn 4× so với `us-east-1`.
  - Đối với training và batch jobs (không nhạy cảm độ trễ), việc lập lịch sang `europe-north1` hoặc `us-east-wa` mang lại lợi ích kép cả về chi phí lẫn phát thải.

---

## 6. Lộ trình Hành động Khuyến nghị cho FinOps Lead NimbusAI

Nếu đảm nhận vai trò FinOps Lead tại NimbusAI, 3 hành động ưu tiên cao nhất theo thứ tự ROI sẽ là:

### Hành động 1: Chuyển đổi Cơ chế Mua sắm (Purchasing Tier Migration) — Ưu tiên: Tuần 1
- **Hành động:** Ký cam kết Reserved Instances 3 năm cho 3 cụm serving cố định (Chat A10G, RAG A100, Search L4) và chuyển 100% training LLM/Embedding sang Spot Instances kết hợp checkpointing.
- **Thời gian hoàn vốn:** Tức thì.
- **Giá trị:** Thu về ngay lập tức **$10,040 / tháng** (chiếm 80% tiềm năng tiết kiệm của toàn công ty).

### Hành động 2: Kích hoạt Cascade Routing & Prompt Caching Gateway — Ưu tiên: Tuần 2
- **Hành động:** Thiết lập router LLM phân tầng tự động (LiteLLM proxy / vLLM Cascade) để chuyển 80% prompt đơn giản sang model nhỏ và tự động cache System Prompts dùng chung cho team Chat & RAG.
- **Giá trị:** Cắt giảm **82.6%** chi phí suy luận hàng ngày, hạ đơn giá xuống còn **$1.126 / 1M-token**.

### Hành động 3: Áp dụng Chính sách Tự động Hóa Hạ tầng (Automated Governance & Right-sizing) — Ưu tiên: Tháng 1
- **Hành động:**
  1. Cấu hình auto-scaler thu hồi GPU sau 15 phút idle (loại bỏ $600/tháng lãng phí ban đêm).
  2. Right-size node `gpu-h100-4` sang A100 và node `gpu-a10g-1` sang L4 (tiết kiệm $655/tháng cho nhóm util-lies; mở rộng lên $1,063.20/tháng khi kết hợp tắt idle cho toàn bộ fleet memory-bound hoặc $1,195.20/tháng ở kịch bản 24h standalone).
  3. Bắt buộc gắn tag 100% trên Kubernetes / Cloud Provider để thực thi Chargeback minh bạch.
- **Giá trị:** Khép kín toàn bộ lỗ hổng lãng phí tài nguyên, xây dựng văn hóa trách nhiệm tài chính bền vững tại NimbusAI.
